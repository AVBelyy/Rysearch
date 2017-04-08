//  Constants for displayMode function:
MODE_MAP = 0,      // Display map only.
MODE_DOCS = 1;     // Display documents and recommendations.

//  The dictionary with the information about topics.
var topicsData;

// FoamTree control object.
var foamtree;

// Initialize FoamTree after the whole page loads to make sure
// the element has been laid out and has non-zero dimensions.
window.addEventListener("load", function() {
    // Load topic hierarchy.
    $.ajax({url: "/get-topics", success: function(result) {
        topicsData = result;
        initializeKnowledgeMap();
    }});

    // TODO: temporary switch
    $(".brand").click(function() {
        displayMode(MODE_MAP);
    });
});

function displayMode(mode) {
    var mapContainer = document.getElementById("knowledge_map_container"),
        overviewContainer = document.getElementById("overview_container"),
        documentContainer = d3.select(document.getElementById("document_container")),
        recommendationsContainer = d3.select(document.getElementById("recommendations_container"));

    recommendationsContainer.selectAll("ul").remove();
    documentContainer.selectAll("h1").remove();
    documentContainer.selectAll("p").remove();

    switch (mode) {
        case MODE_MAP:
            mapContainer.style.display = "inherit";
            overviewContainer.style.display = "none";
            foamtree.zoom(foamtree.get("dataObject"));
            break;
        case MODE_DOCS:
            mapContainer.style.display = "none";
            overviewContainer.style.display = "inherit";
            break;
    }
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
            filterer = function(t) {
                return t["level_id"] == levelId && t["parents"].length == 0;
            };
        } else {
            filterer = function(t) {
                return t["level_id"] == levelId && t["parents"].indexOf(parentName) != -1;
            };
        }
        var response = [];
        for (var topicId in topicsData) {
            var topic = topicsData[topicId];
            if (filterer(topic)) {
                var tw = topic["top_words"].map(function(s) { return s.replace(/_/g, " "); });
                var p1 = tw.slice(0, tw.length - 1).join(", ");
                var p2 = tw[tw.length - 1];
                response.push({
                    label: [p1, p2].join(" и "),
                    id: topicId,
                    isLastLevel: topic["level_id"] == maxLevel,
                    groups: getTopicGroups(levelId + 1, topicId),
                    weight: topic["weight"]
                });
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

        onGroupHold: function(e) {
            if (!e.secondary && e.group.isLastLevel && !e.group.groups) {
                loader.loadDocuments(e.group);
            } else {
                this.open({ groups: e.group, open: !e.secondary });
            }
        },

        // Dynamic loading of groups does not play very well with expose.
        // Therefore, when the user double-clicks a group, initiate data loading
        // if needed and zoom in to the group.
        onGroupDoubleClick: function(e) {
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
    window.addEventListener("resize", (function() {
      var timeout;
      return function() {
        window.clearTimeout(timeout);
        timeout = window.setTimeout(foamtree.resize, 100);
      }
    })());

    //
    // A simple utility for simulating the Ajax loading of data
    // and updating FoamTree with the newly loaded data.
    //
    var loader = (function(foamtree) {
        return {
            loadDocuments: function(group) {
                if (!group.groups && !group.loading) {
                    spinner.start(group);

                    $.ajax({url: "/get-documents?topic_id=" + group.id,
                        success: function(result) {
                            group.groups = [];
                            for (var i in result) {
                                var doc = result[i];
                                var label = doc.title;
                                group.groups.push({
                                    label: label,
                                    id: doc.doc_id,
                                    isDoc: true
                                });
                            }

                            foamtree.open({ groups: group, open: true }).then(function() {
                                spinner.stop(group);
                            });
                        }});
                }
            },

            showOverview: function(group) {
                onclickDocumentCell(group.id);
            }
        };
    })(foamtree);

    // A simple utility for starting and stopping spinner animations
    // inside groups to show that some content is loading.
    var spinner = (function(foamtree) {
        // Set up a groupContentDecorator that draws the loading spinner
        foamtree.set("wireframeContentDecorationDrawing", "always");
        foamtree.set("groupContentDecoratorTriggering", "onSurfaceDirty");
        foamtree.set("groupContentDecorator", function(opts, props, vars) {
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
            start: function(group) {
                group.loading = true;
                group.loadingStartTime = Date.now();

                // Initiate the spinner animation
                foamtree.redraw(true, group);
            },

            stop: function(group) {
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

    recommendationBlocks.on("click", function(doc) { return onclickDocumentCell(doc.doc_id); });
    recommendationBlocks.append("h6")
        .attr("class", "recommendation_title")
        .text(function(doc) {
            return doc.title;
        });
    recommendationBlocks.append("p")
        .attr("class", "recommendation_text")
        .text(function(doc) {
            // TODO: fix when we have authors_names in Habrahabr
            return doc.modalities.authors.join(", ");
        });
}

function displayDocument(doc) {
    var documentContainer = d3.select(document.getElementById("document_container"));
    var docText = doc.markdown.replace(new RegExp("\n+", "g"), "<br><br>");
    var docTags = doc.modalities.flat_tag.map(function(t) { return "<u>" + t + "</u>"; })
    documentContainer.append("h1")
        .attr("align", "center")
        .attr("class", "document_title")
        .text(doc.title);
    documentContainer.append("h1")
        .attr("align", "center")
        .attr("class", "document_authors")
        // TODO: fix when we have authors_names in Habrahabr
        .text(doc.modalities.authors.join(", "));
    documentContainer.append("p")
        .attr("align", "right")
        .attr("class", "document_tags")
        .html(docTags.join(", "));
    documentContainer.append("p")
        .attr("class", "document_text")
        .html(docText);
}

function onclickDocumentCell(doc_id) {
    displayMode(MODE_DOCS);
    $.ajax({url: "/get-document?doc_id=" + doc_id,
            success: function(doc) {
                displayDocument(doc);
                $.ajax({url: "/get-recommendations?doc_id=" + doc.doc_id,
                        success: function(result) {
                            displayRecommendations(doc, result);
                       }});
           }});
}
