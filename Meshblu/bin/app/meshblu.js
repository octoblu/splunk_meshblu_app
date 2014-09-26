(function() {
    var fs              = require("fs");
    var path            = require("path");
    var splunkjs        = require("splunk-sdk");
    var Async           = splunkjs.Async;
    var ModularInputs   = splunkjs.ModularInputs;
    var Logger          = ModularInputs.Logger;
    var Event           = ModularInputs.Event;
    var Scheme          = ModularInputs.Scheme;
    var Argument        = ModularInputs.Argument;
    var utils           = ModularInputs.utils;

    // The version number should be updated every time a new version of the JavaScript SDK is released.
    var SDK_UA_STRING = "splunk-sdk-javascript/1.6.0";

    // Create easy to read date format.
    function getDisplayDate(date) {
        var monthStrings = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

        date = new Date(date);

        var hours = date.getHours();
        if (hours < 10) {
            hours = "0" + hours.toString();
        }
        var mins = date.getMinutes();
        if (mins < 10) {
            mins = "0" + mins.toString();
        }

        return monthStrings[date.getMonth()] + " " + date.getDate() + ", " + date.getFullYear() +
            " - " + hours + ":" + mins + " " + (date.getUTCHours() < 12 ? "AM" : "PM");
    }

    exports.getScheme = function() {
        var scheme = new Scheme("Meshblu");

        scheme.description = "Streams events from a Meshblu Instance";
        scheme.useExternalValidation = true;
        scheme.useSingleInstance = false; // Set to false so an input can have an optional interval parameter.

        scheme.args = [
            new Argument({
                name: "meshblu_server",
                dataType: Argument.dataTypeString,
                description: "The Meshblu Server to connect to",
                requiredOnCreate: true,
                requiredOnEdit: false
            }),
            new Argument({
                name: "server_uuid",
                dataType: Argument.dataTypeString,
                description: "User UUID to connect to the server.",
                requiredOnCreate: true,
                requiredOnEdit: false
            }),
            new Argument({
                name: "server_token",
                dataType: Argument.dataTypeString,
                description: "The Access token associated with the User UUID to permit access to the Meshblu Server",
                requiredOnCreate: true,
                requiredOnEdit: false
            }),
            new Argument({
                name: "operation",
                dataType: Argument.dataTypeString,
                description: "The operation to perform from the API specification. Supported Operations are: subscribe, message, devices, localdevices, status, events",
                requiredOnCreate: true,
                requiredOnEdit: false
            }),
            new Argument({
                name: "device_uuid",
                dataType: Argument.dataTypeString,
                description: "The Device UUID to query against. If the API supports wildcards, use *.",
                requiredOnCreate: true,
                requiredOnEdit: false
            }),
            new Argument({
                name: "device_token",
                dataType: Argument.dataTypeString,
                description: "The device UUID for the following operations: subscribe, events.",
                requiredOnCreate: false,
                requiredOnEdit: false
            }),

        ];

        return scheme;
    };

    exports.validateInput = function(definition, done) {
        var owner = definition.parameters.owner;
        var repository = definition.parameters.repository;
        var token = definition.parameters.token;

        var Github = new GithubAPI({version: "3.0.0"});

        try {
            // Authenticate with the access token if it was provided.
            if (token && token.length > 0) {
                Github.authenticate({
                    type: "oauth",
                    token: token
                });
            }

            Github.repos.getCommits({
                headers: {"User-Agent": SDK_UA_STRING},
                user: owner,
                repo: repository,
                per_page: 1, // The minimum per page value supported by the Github API.
                page: 1
            }, function (err, res) {
                if (err) {
                    done(err);
                }
                else {
                    // If we get any kind of message, that's a bad sign.
                    if (res.message) {
                        done(new Error(res.message));
                    }
                    // We got exactly what we expected.
                    else if (res.length === 1 && res[0].hasOwnProperty("sha")) {
                        done();
                    }
                    else {
                        done(new Error("Expected only the latest commit, instead found " + res.length + " commits."));
                    }
                }
            });
        }
        catch (e) {
            done(e);
        }
    };

    exports.streamEvents = function(name, singleInput, eventWriter, done) {
        // Get the checkpoint directory out of the modular input's metadata.
        var checkpointDir = this._inputDefinition.metadata["checkpoint_dir"];

        var owner = singleInput.owner;
        var repository = singleInput.repository;
        var token      = singleInput.token;

        var alreadyIndexed = 0;

        var Github = new GithubAPI({version: "3.0.0"});

        if (token && token.length > 0) {
            Github.authenticate({
                type: "oauth",
                token: token
            });
        }

        var page = 1;
        var working = true;

        Async.whilst(
            function() {
                return working;
            },
            function(callback) {
                try {
                    Github.repos.getCommits({
                        headers: {"User-Agent": SDK_UA_STRING},
                        user: owner,
                        repo: repository,
                        per_page: 100, // The maximum per page value supported by the Github API.
                        page: page
                    }, function (err, res) {
                        if (err) {
                            callback(err);
                            return;
                        }
                        // When res.meta.link doesn't contain "next", we should stop the loop after streaming commits on this page.
                        if (res.meta.link.indexOf("rel=\"next\"") < 0) {
                            working = false;
                        }

                        var checkpointFilePath  = path.join(checkpointDir, owner + " " + repository + ".txt");
                        var checkpointFileNewContents = "";
                        var errorFound = false;

                        // Set the temporary contents of the checkpoint file to an empty string
                        var checkpointFileContents = "";
                        try {
                            checkpointFileContents = utils.readFile("", checkpointFilePath);
                        }
                        catch (e) {
                            // If there's an exception, assume the file doesn't exist
                            // Create the checkpoint file with an empty string
                            fs.appendFileSync(checkpointFilePath, "");
                        }

                        for (var i = 0; i < res.length && !errorFound; i++) {
                            var json = {
                                sha: res[i].sha,
                                api_url: res[i].url,
                                url: "https://github.com/" + owner + "/" + repository + "/commit/" + res[i].sha
                            };
                                                
                            // If the file exists and doesn't contain the sha, or if the file doesn't exist.
                            if (checkpointFileContents.indexOf(res[i].sha + "\n") < 0) {
                                var commit = res[i].commit;

                                // At this point, assumed checkpoint doesn't exist.
                                json.message = commit.message.replace(/(\n|\r)+/g, " "); // Replace newlines and carriage returns with spaces.
                                json.author = commit.author.name;
                                json.rawdate = commit.author.date;
                                json.displaydate = getDisplayDate(commit.author.date.replace("T|Z", " ").trim());

                                try {
                                    var event = new Event({
                                        stanza: repository,
                                        sourcetype: "github_commits",
                                        data: JSON.stringify(json), // Have Splunk index our event data as JSON.
                                        time: Date.parse(json.rawdate) // Set the event timestamp to the time of the commit.
                                    });
                                    eventWriter.writeEvent(event);
                                    
                                    checkpointFileNewContents += res[i].sha + "\n"; // Append this commit to the string we'll write at the end
                                    Logger.info(name, "Indexed a Github commit with sha: " + res[i].sha);
                                }
                                catch (e) {
                                    errorFound = true;
                                    working = false; // Stop streaming if we get an error.
                                    Logger.error(name, e.message);
                                    fs.appendFileSync(checkpointFilePath, checkpointFileNewContents); // Write to the checkpoint file
                                    done(e);

                                    // We had an error, die.
                                    return;
                                }
                            }
                            else {
                                // The commit has already been indexed
                                alreadyIndexed++;
                            }
                        }

                        fs.appendFileSync(checkpointFilePath, checkpointFileNewContents); // Write to the checkpoint file
                        
                        if (alreadyIndexed > 0) {
                            Logger.info(name, "Skipped " + alreadyIndexed.toString() + " already indexed Github commits from " + owner + "/" + repository);
                        }
                        
                        page++;
                        alreadyIndexed = 0;
                        callback();
                    });
                }
                catch (e) {
                    callback(e);
                }
            },
            function(err) {
                // We're done streaming.
                done(err);
            }
        );
    };

    ModularInputs.execute(exports, module);
})();
