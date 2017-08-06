//  Constants for displayMode function:
var currentMode;
MODE_MAP = 0;        // Display map only.
MODE_DOCS = 1;       // Display documents and recommendations.
MODE_ASSESS = 2;     // Display documents and assessor controls.

//  The dictionary with the information about topics.
var topicsData;

// FoamTree control object.
var foamtree;

// Current assessor-mode state.
var assess;

// Search field typing timer.
var typingTimer;
var doneTypingInterval = 200;

// Initial weights of topics.
var initialTopicsWeights = {};

// the element has been laid out and has non-zero dimensions.
$(document).ready(function () {
    // Load topic hierarchy.
    $.get({url: "/get-topics",
        success: function (result) {
            topicsData = result.ok;
            initializeKnowledgeMap();
        }});

    $("#home-btn").click(function () {
        displayMode(MODE_MAP);
    });

    $("#search_text").keypress(function (e) {
        if (e.which == 13) {
            e.preventDefault();
        }
    });

    $("#search_text").on("input", function() {
        clearTimeout(typingTimer);
        if ($("#search_text").val()) {
            typingTimer = setTimeout(onPerformSearchQuery, doneTypingInterval);
        } else {
            resetHighlight();
        }
    });

    $("#upload_btn").click(function() {
        if ($(this).hasClass("disabled")) {
            return false;
        }
    });

    $("#upload_hidden").change(function () {
        // TODO: check for XHR2 browser support
        var formData = new FormData();
        formData.append(this.name, this.files[0]);
        this.value = "";

        $("#upload_btn").addClass("disabled");
        $("#upload_caption").removeClass("glyphicon-upload");
        $("#upload_caption").addClass("glyphicon-refresh glyphicon-refresh-animate");

        $.ajax({
            url: "/transform-doc",
            type: "POST",
            data: formData,
            processData: false,
            contentType: false,
            cache: false,
            success: function (result) {
                if (result.ok) {
                    var theta = result.ok.theta;
                    highlightTopics(theta);
                } else {
                    // TODO: error handling
                    alert("Error: " + result.error.message);
                }
                $("#upload_btn").removeClass("disabled");
                $("#upload_caption").addClass("glyphicon-upload");
                $("#upload_caption").removeClass("glyphicon-refresh glyphicon-refresh-animate");
            }
        });

        return false;
    });
    /*$("#upload_btn").fileinput({
        uploadUrl: "/transform-doc",
        showPreview: false,
        maxFileCount: 1,
        autoReplace: true,
        previewFileType: "text",
        allowedFileExtensions: ["txt", "md"],
        showCaption: false,
    }).on("fileuploaded", function(e, data, previewId, index) {
    });*/
});

function displayMode(mode) {
    var mapContainer = document.getElementById("knowledge_map_container"),
        searchTextContainer = document.getElementById("search_text_container"),
        overviewContainer = document.getElementById("overview_container"),
        documentContainer = d3.select(document.getElementById("document_container")),
        recommendationsContainer = d3.select(document.getElementById("recommendations_container"));

    recommendationsContainer.selectAll("ul").remove();
    documentContainer.selectAll("h1").remove();
    documentContainer.selectAll("p").remove();

    $(document).unbind("keyup");

    switch (mode) {
        case MODE_MAP:
            mapContainer.style.display = "inherit";
            searchTextContainer.style.display = "inherit";
            overviewContainer.style.display = "none";
            foamtree.zoom(foamtree.get("dataObject"));
            break;
        case MODE_DOCS:
            mapContainer.style.display = "none";
            searchTextContainer.style.display = "none";
            overviewContainer.style.display = "inherit";
            break;
        case MODE_ASSESS:
            mapContainer.style.display = "none";
            searchTextContainer.style.display = "none";
            overviewContainer.style.display = "inherit";
            handleAssessKeys();
            break;
    }

    currentMode = mode;
}

/*  Function that starts initialization of knowledge map and other elements of interface. */
function initializeKnowledgeMap() {
    // Initialize FoamTree

    // Calculate number of levels.
    var maxLevel = 0;
    for (var topicId in topicsData) {
        maxLevel = Math.max(maxLevel, topicsData[topicId]["level_id"]);
    }

    function initGroupsData(levelId, parentName) {
        // TODO: rewrite (O(|T|^2) complexity)
        var filterer;
        if (parentName === undefined) {
            filterer = function (t) {
                return t["level_id"] == levelId && t["parents"].length == 0;
            };
        } else {
            filterer = function (t) {
                return t["level_id"] == levelId && t["parents"].indexOf(parentName) != -1;
            };
        }
        var response = [];
        var siblingsCount = 0;
        for (var topicId in topicsData) {
            var topic = topicsData[topicId];
            if (topic["level_id"] == levelId) {
                siblingsCount++;
            }
        }
        for (var topicId in topicsData) {
            var topic = topicsData[topicId];
            if (filterer(topic)) {
                // Topic weight corresponds to number of topic's articles
                // We do not want empty topics on the map
                if (topic["weight"] > 0 || levelId == 0) {
                    var tw = topic["top_words"].map(function (s) { return s.replace(/_/g, " "); });
                    var p1 = tw.slice(0, tw.length - 1).join(", ");
                    var p2 = tw[tw.length - 1];
                    var isLastLevel = topic["level_id"] == maxLevel;
                    var w = 1; //Math.log(1 + topic["weight"])
                    response.push({
                        label: [p1, p2].join(" и "),
                        id: topicId,
                        groupType: isLastLevel ? "last_level" : "level",
                        groups: initGroupsData(levelId + 1, topicId),
                        weight: w,
                        spectrumId: topic["spectrum_id"],
                    });
                    initialTopicsWeights[topicId] = w;
                }
            }
        }
        response.sort(function (a, b) {
            return a["spectrumId"] - b["spectrumId"];
        });
        return response.length ? response : undefined;
    }

    foamtree = new CarrotSearchFoamTree({
        id: "knowledge_map_container",
        parentFillOpacity: 0.9,
        rolloutDuration: 0,
        pullbackDuration: 0,

        relaxationVisible: true,
        relaxationMaxDuration: 1000,
        relaxationInitializer: "ordered",

        groupMinDiameter: 0,
        groupBorderWidth: 2,
        groupStrokeWidth: 1,
        groupInsetWidth: 3,
        groupSelectionOutlineWidth: 4,

        onGroupHold: function (e) {
            if (!e.secondary && e.group.groupType == "last_level" && !e.group.groups) {
                loader.loadDocuments(e.group);
            } else {
                this.open({ groups: e.group, open: !e.secondary });
            }
        },

        // Dynamic loading of groups does not play very well with expose.
        // Therefore, when the user double-clicks a group, initiate data loading
        // if needed and zoom in to the group.
        onGroupDoubleClick: function (e) {
            e.preventDefault();
            var group = e.secondary ? e.bottommostOpenGroup : e.topmostClosedGroup;
            var toZoom;
            if (group) {
                // Open on left-click, close on right-click
                if (!e.secondary && group.groupType == "last_level" && !e.group.groups) {
                    loader.loadDocuments(group);
                } else if (!e.secondary && group.groupType == "doc") {
                    loader.showOverview(group);
                } else {
                    this.open({ groups: group, open: !e.secondary });
                }
                toZoom = e.secondary ? group.parent : group;
            } else {
                toZoom = this.get("dataObject");
            }
            this.zoom(toZoom);
        },

        dataObject: {
            groups: initGroupsData(0)
        },

        groupColorDecorator: function (opts, params, vars) {
            if (params.group.color) {
                vars.groupColor = params.group.color;
            }
        }
    });

    // Resize FoamTree on orientation change
    window.addEventListener("orientationchange", foamtree.resize);

    // Resize on window size changes
    window.addEventListener("resize", (function () {
        var timeout;
        return function () {
            window.clearTimeout(timeout);
            timeout = window.setTimeout(foamtree.resize, 100);
        }
    })());

    //
    // A simple utility for simulating the AJAX loading of data
    // and updating FoamTree with the newly loaded data.
    //
    var loader = (function (foamtree) {
        return {
            loadDocumentPage: function (docs, weights, offset, limit) {
                var groups = [];
                var pageDocs;

                if (offset + limit < docs.length) {
                    pageDocs = docs.slice(offset, offset + limit - 1);
                } else {
                    pageDocs = docs.slice(offset);
                }

                var sumWeights = 0;
                for (var i in pageDocs) {
                    var doc = pageDocs[i];
                    var w = weights[doc.doc_id];
                    var label = doc.title;
                    sumWeights += w;
                    groups.push({
                        label: label,
                        id: doc.doc_id,
                        groupType: "doc",
                        weight: w
                    });
                }

                if (offset + limit < docs.length) {
                    var remainingCount = docs.length - offset - limit;
                    groups.push({
                        label: "...",
                        groupType: "scroll_page",
                        groups: loader.loadDocumentPage(docs, weights, offset + limit, limit),
                        weight: sumWeights / 2
                    });
                }

                return groups;
            },
            loadDocuments: function (group) {
                if (!group.groups && !group.loading) {
                    spinner.start(group);

                    var docsCount = Math.min(topicsData[group.id]["weight"], 200);
                    $.get({url: "/get-documents",
                        data: { topic_id: group.id, offset: 0, limit: docsCount },
                        success: function (result) {
                            var docs = result.ok.docs;
                            var weights = result.ok.weights;
                            group.groups = loader.loadDocumentPage(docs, weights, 0, 10);
                            foamtree.open({ groups: group, open: true }).then(function () {
                                spinner.stop(group);
                            });
                        }});
                }
            },

            showOverview: function (group) {
                onclickDocumentCell(group.id);
            }
        };
    })(foamtree);

    // A simple utility for starting and stopping spinner animations
    // inside groups to show that some content is loading.
    var spinner = (function (foamtree) {
        // Set up a groupContentDecorator that draws the loading spinner
        foamtree.set("wireframeContentDecorationDrawing", "always");
        foamtree.set("groupContentDecoratorTriggering", "onSurfaceDirty");
        foamtree.set("groupContentDecorator", function (opts, props, vars) {
            var group = props.group;
            if (!group.loading) {
                return;
            }

            // Draw the spinner animation

            // The center of the polygon
            var cx = props.polygonCenterX;
            var cy = props.polygonCenterY;

            // Drawing context
            var ctx = props.context;

            // We'll advance the animation based on the current time
            var now = Date.now();

            // Some simple fade-in of the spinner
            var baseAlpha = 0.3;
            if (now - group.loadingStartTime < 500) {
                baseAlpha *= Math.pow((now - group.loadingStartTime) / 500, 2);
            }

            // If polygon changed, recompute the radius of the spinner
            if (props.shapeDirty || group.spinnerRadius == undefined) {
                // If group's polygon changed, recompute the radius of the inscribed polygon.
                group.spinnerRadius = CarrotSearchFoamTree.geometry.circleInPolygon(props.polygon, cx, cy) * 0.4;
            }

            // Draw the spinner
            var angle = 2 * Math.PI * (now % 1000) / 1000;
            ctx.globalAlpha = baseAlpha;
            ctx.beginPath();
            ctx.arc(cx, cy, group.spinnerRadius, angle, angle + Math.PI / 5, true);
            ctx.strokeStyle = "black";
            ctx.lineWidth = group.spinnerRadius * 0.3;
            ctx.stroke();

            // Schedule the group for redrawing
            foamtree.redraw(true, group);
        });

        return {
            start: function (group) {
                group.loading = true;
                group.loadingStartTime = Date.now();

                // Initiate the spinner animation
                foamtree.redraw(true, group);
            },

            stop: function (group) {
                group.loading = false;
            }
        };
    })(foamtree);

    displayMode(MODE_MAP);
}

function initializeDocSunburst(theta, filename) {
    /*
    // We respin until the visualization container has non-zero area (there are race
    // conditions on Chrome which permit that) and the visualization class is loaded.
    var container = document.getElementById("visualization");
    if (container.clientWidth <= 0 || container.clientHeight <= 0 || !window["CarrotSearchCircles"]) {
    window.setTimeout(embed, 250);
    return;
}
    */

    var pairs = Object.keys(theta).map(function (tid) {
        return [tid, theta[tid], topicsData[tid].spectrum_id];
    }).sort(function (a, b) {
        return b[1] - a[1];
    });
    function initGroupsData(levelId, parentName) {
        var groups = [];
        var filterer;
        if (parentName === undefined) {
            filterer = function (t) {
                return t["level_id"] == levelId && t["parents"].length == 0;
            };
        } else {
            filterer = function (t) {
                return t["level_id"] == levelId && t["parents"].indexOf(parentName) != -1;
            };
        }
        for (var i = 0; i < pairs.length; i++) {
            var topicId = pairs[i][0], topicWeight = pairs[i][1], topicSpectrumId = pairs[i][2];
            if (topicId in topicsData && filterer(topicsData[topicId])) {
                topicName = topicsData[topicId]["top_words"].join(", ");
                groups.push({label: topicName,
                             weight: topicWeight,
                             spectrumId: topicSpectrumId,
                             groups: initGroupsData(levelId + 1, topicId)});
                if (groups.length >= 5) {
                    break;
                }
            }
        }
        groups = groups.sort(function (a, b) {
            return a.spectrumId - b.spectrumId;
        });
        return groups;
    }

    // Use the defaults for all parameters.
    var circles = new CarrotSearchCircles({
        id: "doc_sunburst_container",
        captureMouseEvents: false,
        pixelRatio: Math.min(1.5, window.devicePixelRatio || 1),
        dataObject: {
            groups: initGroupsData(0)
        }
    });

    circles.set({
        titleBar: "inscribed",
        //diameter: "60%",
        titleBarTextColor: "#000",
        //rainbowStartColor: "#2E8B57",
        //rainbowEndColor: "#98FB98",
        titleBarLabelDecorator: function (attrs) {
            attrs.label = filename;
        }
    });

    // TODO: install resize hook later
    //installResizeHandlerFor(circles, 0);
}

function displayRecommendations(doc, recommendationsData) {
    var recommendationsContainer = d3.select(document.getElementById("recommendations_container"));

    var recommendationBlocks = recommendationsContainer.append("ul")
        .attr("class", "thumbnails")
        .selectAll("li").data(recommendationsData).enter()
    //.append("li").attr("class", "span10")
        .append("a").attr("class", "thumbnail");

    recommendationBlocks.on("click", function (doc) { return onclickDocumentCell(doc.doc_id); });
    recommendationBlocks.append("h6")
        .attr("class", "recommendation_title")
        .text(function (doc) {
            return doc.title;
        });
    recommendationBlocks.append("p")
        .attr("class", "recommendation_text")
        .text(function (doc) {
            return doc.authors_names.join(", ");
        });
}

function displayDocument(doc) {
    var documentContainer = d3.select(document.getElementById("document_container"));
    var docText = doc.markdown.replace(new RegExp("\n+", "g"), "<br><br>");
    var docTags = doc.modalities.flat_tag.map(function (t) { return "<u>" + t + "</u>"; })
    documentContainer.append("h1")
        .attr("align", "center")
        .attr("class", "document_title")
        .text(doc.title);
    documentContainer.append("h1")
        .attr("align", "center")
        .attr("class", "document_authors")
        .text(doc.authors_names.join(", "));
    documentContainer.append("p")
        .attr("align", "right")
        .attr("class", "document_tags")
        .html(docTags.join(", "));
    if (doc.recommended_tags) {
        var recommTags = doc.recommended_tags.map(function (t) { return "<u>" + t + "</u>"; })
        documentContainer.append("p")
            .attr("align", "right")
            .attr("class", "document_tags")
            .html(recommTags.join(", "));
    }
    documentContainer.append("p")
        .attr("class", "document_text")
        .html(docText);
}

function onclickDocumentCell(doc_id) {
    displayMode(MODE_DOCS);
    $.get({url: "/get-document",
        data: { doc_id: doc_id, recommend_tags: true },
        success: function (result) {
            var doc = result.ok;
            displayDocument(doc);
            $.get({url: "/recommend-docs",
                data: { doc_id: doc.doc_id },
                success: function (result) {
                    var recommendations = result.ok;
                    displayRecommendations(doc, recommendations);
                }});
        }});
}

function onPerformSearchQuery() {
    var query = $("#search_text").val();
    $.get({url: "/perform-search",
        data: {query: query, limit: 100},
        success: function (result) {
            if (result.ok) {
                theta = result.ok;
                highlightTopics(theta);
            } else {
                // TODO: error handling
                alert("Error: " + result.error.message);
            }
        }
    })
 }

function onclickAssessorMode() {
    var assessorId = 0;   // TODO: set from URL hash-part
    var assessorsCnt = 1; // TODO: set from URL hash-part
    var collectionName = "habrahabr";

    displayMode(MODE_ASSESS);

    $.get({url: "/get-next-assessment",
        data: {
            assessor_id: assessorId,
            assessors_cnt: assessorsCnt,
            collection_name: collectionName
        },
        success: function (docsIds) {
            assess = {};
            assess["ids"] = docsIds;
            assess["zero_docs_flag"] = docsIds.length == 0;
            showNextAssessment();
        }});
}

function showNextAssessment() {
    if (!assess) {
        alert("Нет документов для разметки");
        return;
    }
    if (assess["ids"].length == 0) {
        if (assess["zero_docs_flag"]) {
            alert("Все документы этой коллекции уже размечены");
        } else {
            // Получим очередную порцию документов
            onclickAssessorMode();
        }
        return;
    }

    var nextDocId = assess["ids"][assess["ids"].length - 1];

    // Очистим холст
    displayMode(MODE_ASSESS);

    $.get({url: "/get-document",
        data: { doc_id: nextDocId },
        success: function (doc) {
            // Display document
            displayDocument(doc);

            // Display controls
            var recommendationsContainer = d3.select(document.getElementById("recommendations_container"));

            var recommendationBlocks = recommendationsContainer.append("ul")
                .attr("class", "thumbnails");

            recommendationBlocks.append("a").attr("class", "thumbnail").append("h6")
                .on("click", onclickAssessRelevant)
                .attr("class", "recommendation_title")
                .text("Документ релевантен (Ctrl + Right)");

            recommendationBlocks.append("a").attr("class", "thumbnail").append("h6")
                .on("click", onclickAssessIrrelevant)
                .attr("class", "recommendation_title")
                .text("Документ не релевантен (Ctrl + Left)");

            recommendationBlocks.append("a").attr("class", "thumbnail").append("h6")
                .on("click", onclickAssessSkip)
                .attr("class", "recommendation_title")
                .text("Пропустить документ (Ctrl + Space)");
        }});
}

function handleAssessKeys() {
    $(document).keyup(function (e) {
        if (e.keyCode == 37 && e.ctrlKey) {
            onclickAssessIrrelevant();
        } else if (e.keyCode == 39 && e.ctrlKey) {
            onclickAssessRelevant();
        } else if (e.keyCode == 32 && e.ctrlKey) {
            onclickAssessSkip();
        }
    });
}

function onclickAssessRelevant() {
    if (!assess || assess["ids"].length == 0) {
        return;
    }

    var nextDocId = assess["ids"][assess["ids"].length - 1];
    $.post({url: "/assess-document",
        data: { doc_id: nextDocId, is_relevant: true }
    });

    assess["ids"].pop();
    showNextAssessment();
}

function onclickAssessIrrelevant() {
    if (!assess || assess["ids"].length == 0) {
        return;
    }

    var nextDocId = assess["ids"][assess["ids"].length - 1];
    $.post({url: "/assess-document",
        data: { doc_id: nextDocId, is_relevant: false }
    });

    assess["ids"].pop();
    showNextAssessment();
}

function onclickAssessSkip() {
    if (!assess || assess["ids"].length == 0) {
        return;
    }

    assess["ids"].pop();
    showNextAssessment();
}

function rainbowColormap(maxValue) {
    return function(i) {
        var hue = i / maxValue * 360;
        return "hsl(" + hue + ", 100%, 50%)";
    }
}

function highlightTopics(theta) {
    // Set weights for topics
    var maxStartWeight = 1;
    var minWeightMultiplier = 0.5;
    var topNTopics = [5, 1]; // TODO: level-dependent constant, fix.
    var items = Object.keys(theta).map(function (k) { return [k, theta[k]]; });
    items.sort(function (a, b) { return b[1] - a[1]; });
    var weights = {};
    var maxWeights = {};
    var minWeights = {};
    var counts = {};
    for (var i = 0; i < items.length; i++) {
        var topicId = items[i][0], weight = Math.log(1 + items[i][1]);
        var parentTopic;
        if (topicId in topicsData && topicId.startsWith("level_0")) {
            parentTopic = "top";
        } else if (topicId in topicsData && topicsData[topicId]["parents"]) {
            parentTopic = topicsData[topicId]["parents"][0];
        } else {
            continue;
        }
        if (!(parentTopic in maxWeights)) {
            maxWeights[parentTopic] = weight;
            counts[parentTopic] = 0;
        }
        var levelId = topicsData[topicId]["level_id"];
        if (counts[parentTopic] < topNTopics[levelId]) {
            minWeights[parentTopic] = weight / maxWeights[parentTopic];
            weights[topicId] = minWeights[parentTopic] * maxStartWeight;
            counts[parentTopic]++;
        } else {
            weights[topicId] = minWeights[parentTopic] * minWeightMultiplier;
        }
    }
    // Update weights on the knowledge map
    var dataObject = foamtree.get("dataObject");
    var updateWeights = function (groups) {
        for (var i in groups) {
            var group = groups[i];
            if (group["groupType"] == "level" || group["groupType"] == "last_level") {
                var gid = group["id"];
                if (gid in weights) {
                    group["weight"] = weights[gid];
                    foamtree.redraw(false, group);
                }
                if (group["groupType"] == "level") {
                    updateWeights(group["groups"]);
                }
            }
        }
    };
    updateWeights(dataObject["groups"]);
    foamtree.update();
}

function resetHighlight() {
    // Update weights on the knowledge map
    var dataObject = foamtree.get("dataObject");
    var updateWeights = function (groups) {
        for (var i in groups) {
            var group = groups[i];
            if (group["groupType"] == "level" || group["groupType"] == "last_level") {
                var gid = group["id"];
                if (gid in initialTopicsWeights) {
                    group["weight"] = initialTopicsWeights[gid];
                    //foamtree.redraw(false, group);
                }
                if (group["groupType"] == "level") {
                    updateWeights(group["groups"]);
                }
            }
        }
    };
    updateWeights(dataObject["groups"]);
    foamtree.set("dataObject", dataObject);
    //foamtree.update();
}
