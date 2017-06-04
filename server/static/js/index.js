//  Constants for displayMode function:
var currentMode;
MODE_MAP = 0,        // Display map only.
MODE_DOCS = 1;       // Display documents and recommendations.
MODE_ASSESS = 2;     // Display documents and assessor controls.
MODE_TRANSFORM = 3;  // Display upload form and document info.

//  The dictionary with the information about topics.
var topicsData;

// FoamTree control object.
var foamtree;

// Current assessor-mode state.
var assess;

// Initialize FoamTree after the whole page loads to make sure
// the element has been laid out and has non-zero dimensions.
window.addEventListener("load", function () {
    // Load topic hierarchy.
    $.get({url: "/get-topics",
            success: function (result) {
                topicsData = result;
                initializeKnowledgeMap();
            }});

    $("#home-btn").click(function () {
        displayMode(MODE_MAP);
    });

    $("#assess-btn").click(onclickAssessorMode);

    $("#transform-btn").click(function () {
        displayMode(MODE_TRANSFORM);
    });

    // TODO: Write proper code
    $("#fileupload").fileupload({
        dataType: "json",
        done: function (e, data) {
            var theta = data.result.theta;
            // TODO: write something more useful
            var pairs = Object.keys(theta).map(function (tid) {
                return [tid, theta[tid]];
            }).sort(function (a, b) {
                return b[1] - a[1];
            });
            var top_topics = "";
            for (var i = 0; i < 3; i++) {
                var topicName;
                if (pairs[i][0] in topicsData) {
                    topicName = topicsData[pairs[i][0]]["top_words"].join(", ");
                } else {
                    topicName = "<b>мусорная тема</b>";
                }
                top_topics += "<li>" + topicName + " (" + parseInt(pairs[i][1] * 100) + "%)</li>";
            }
            $("#demo-text").html("<b>Топ-3 темы документа:</b><br><ul>" + top_topics + "</ul>");
        }
    });
});

function displayMode(mode) {
    var mapContainer = document.getElementById("knowledge_map_container"),
        overviewContainer = document.getElementById("overview_container"),
        documentContainer = d3.select(document.getElementById("document_container")),
        recommendationsContainer = d3.select(document.getElementById("recommendations_container")),
        transformContainer = document.getElementById("transform_container");

    recommendationsContainer.selectAll("ul").remove();
    documentContainer.selectAll("h1").remove();
    documentContainer.selectAll("p").remove();

    $(document).unbind("keyup");

    switch (mode) {
        case MODE_MAP:
            mapContainer.style.display = "inherit";
            overviewContainer.style.display = "none";
            transformContainer.style.display = "none";
            foamtree.zoom(foamtree.get("dataObject"));
            break;
        case MODE_DOCS:
            mapContainer.style.display = "none";
            overviewContainer.style.display = "inherit";
            transformContainer.style.display = "none";
            break;
        case MODE_ASSESS:
            mapContainer.style.display = "none";
            overviewContainer.style.display = "inherit";
            transformContainer.style.display = "none";
            handleAssessKeys();
            break;
        case MODE_TRANSFORM:
            mapContainer.style.display = "none";
            overviewContainer.style.display = "none";
            transformContainer.style.display = "block";
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

    function getTopicGroups(levelId, parentName) {
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
        for (var topicId in topicsData) {
            var topic = topicsData[topicId];
            if (filterer(topic)) {
                // Topic weight corresponds to number of topic's articles
                // We do not want empty topics on the map
                if (topic["weight"] > 0 || levelId == 0) {
                    var tw = topic["top_words"].map(function (s) { return s.replace(/_/g, " "); });
                    var p1 = tw.slice(0, tw.length - 1).join(", ");
                    var p2 = tw[tw.length - 1];
                    response.push({
                        label: [p1, p2].join(" и "),
                        id: topicId,
                        isLastLevel: topic["level_id"] == maxLevel,
                        groups: getTopicGroups(levelId + 1, topicId),
                        weight: Math.log(1 + topic["weight"])
                    });
                }
            }
        }
        return response.length ? response : undefined;
    }

    foamtree = new CarrotSearchFoamTree({
        id: "knowledge_map_container",
        parentFillOpacity: 0.9,
        rolloutDuration: 0,
        pullbackDuration: 0,

        relaxationVisible: true,

        onGroupHold: function (e) {
            if (!e.secondary && e.group.isLastLevel && !e.group.groups) {
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
                if (!e.secondary && group.isLastLevel && !e.group.groups) {
                    loader.loadDocuments(group);
                } else if (!e.secondary && group.isDoc) {
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
            groups: getTopicGroups(0)
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
            loadDocuments: function (group) {
                if (!group.groups && !group.loading) {
                    spinner.start(group);

                    $.get({url: "/get-documents",
                        data: { topic_id: group.id },
                        success: function (result) {
                            var docs = result.docs;
                            var weights = result.weights;
                            group.groups = [];
                            for (var i in docs) {
                                var doc = docs[i];
                                var w = weights[doc.doc_id];
                                var label = doc.title;
                                group.groups.push({
                                    label: label,
                                    id: doc.doc_id,
                                    isDoc: true,
                                    weight: w
                                });
                            }

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
            success: function (doc) {
                displayDocument(doc);
                $.get({url: "/recommend-docs",
                        data: { doc_id: doc.doc_id },
                        success: function (result) {
                            displayRecommendations(doc, result);
                       }});
           }});
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
