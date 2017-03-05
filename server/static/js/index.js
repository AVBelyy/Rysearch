/*  Each cell center is placed in it's own vertex of grid by default.
    Random factor (from 0 to 0.5) determines the radius of circle around the vertex where
    the center will be placed (randomly). The less this constant - the more
    cells look like regular rectangles. */
var random_factor = 0.3
//  The opacity of cells from background.
var opacity_background = 1
//  The opacity of cells from foreground.
var opacity_foreground = 0.95

//  Constants that define what type of cells drawVoronoi() will draw:
//  (Of course it should be more universal then now)
var IS_BACKGROUND = 0, // Draw cells only, without any titles.
    IS_TOPICS = 1,     // Draw cells with topics.
    IS_DOCS = 2,       // Draw cells with documets.

//  Constants for display_mode function:
    MODE_MAP = 0,      // Display map only.
    MODE_DOCS = 1;     // Display documents and recommendations.

//  The dictionary with the information about topics.
var topics_data;

//  Yes, I know that it should be in .css, it's here for debugging.
var yellow_colorscheme = {
    "0": "#FFAE00",
    "1": "#BF9230",
    "2": "#A67100",
    "3": "#FFC340",
    "4": "#FFD373"
}

var mashas_colorscheme = {
    "0": "#6F4B86",
    "1": "#E2B5FF",

    "2": "#C28E67",
    "3": "#FFD2B0",

    "4": "#427D78",
    "5": "#B0FFF9",

    "6": "#C2C167",
    "7": "#FFFEB0",

    "8": "#894AB1",
    "9": "#FFA661",
    "10": "#3EA49C",
    "11": "#FFFD61"
    /*
    //  The saturatest set.
    "1": "#521A76",
    "4": "#AA5D22",
    "7": "#166D67",
    "10": "#AAA822",

    //  The fadest set.
    "4": "#F9F0FF",
    "9": "#FFF6EF",
    "14": "#EFFFFE",
    "19": "#FFFFEF"
    */
}

$.ajax({url: "http://localhost:3000/get-topics", success: function(result) {
    topics_data = result;
    initialize_knowledge_map();
}});

function display_mode(mode) {
    var svg = document.getElementById("knowledge_map_svg_container"),
        document_container = d3.select(document.getElementById("document_container")),
        recommendations_container = d3.select(document.getElementById("recommendations_container"));

    recommendations_container.selectAll("ui").remove();
    document_container.selectAll("h1").remove();
    document_container.selectAll("p").remove();

    switch (mode) {
        case MODE_MAP:
            svg.setAttribute("display", "inherit");
            break;
        case MODE_DOCS:
            svg.setAttribute("display", "none");
            break;
    }
}

/*  Function that starts initialization of knowledge map and other interface elements elements. */
function initialize_knowledge_map() {
    var topic_keys = Object.keys(topics_data);

    display_mode(MODE_MAP);

    /*  Calculate svg canvas size.
    TODO: Exclude hardcoded constant "120" = 2*svg.padding-left (placed in index.css)
    */

    //  SVG canvas for knowledge map drawing.
    var svg_container = document.getElementById("main_container");
    var svg_width = svg_container.offsetWidth - 120,
        svg_height = Number(svg_width * 0.45);
    var svg = d3.select(document.getElementById("knowledge_map_svg_container"));

    svg.attr("width", svg_width).attr("height", svg_height)
       .attr("viewBox", "0 0 " + svg_width + " " + svg_height);

    //  Dummy way to count the number of topic layers.
    var max_level = topic_keys.reduce(function(max, key) {
        return topics_data[key].level_id > max ? topics_data[key].level_id : max;
    }, 0);

    //  Add two fields to all topics: its key and the indicator of bottom layer.
    for (var i = 0; i < topic_keys.length; i++) {
        var key = topic_keys[i],
            topic = topics_data[key];
        topic["key"] = key;
        topic["is_last_level"] = topic.level_id == max_level;
    }

    //  Add imaginary layer with one cell: root.
    topics_data["root"] = {
        "level_id": "-1",
        "top_words": "Root",
        "children": topic_keys.filter(function(key) {
            // TODO: wat?
            return topics_data[key].level_id == String(0);
        })
    }

    //  Draw backgound cells without any titles on it.
    drawVoronoi(svg, [], d3.range(topics_data["root"].children.length * 4),
                opacity_background, IS_BACKGROUND);

    //  Draw cells with top-level topics.
    drawVoronoi(svg, ["root"], topics_data["root"].children.map(function(key) {
        return topics_data[key]
    }), opacity_foreground, IS_TOPICS);
}

//  Update the list of chosen topics on the navigation bar
//  according to the given selected_topics_list.
function updateChosenTopicsList(selected_topics_list, svg) {
    d3.select(document.getElementById('chosen_topics_list'))
      .selectAll("li").remove();
    d3.select(document.getElementById('chosen_topics_list'))
      .selectAll("li").data(selected_topics_list).enter().append("li")
      //.attr("class", "active")
      .append("a").attr("href", "#").text(function(d) {
          return topics_data[d].top_words + " > ";
      })
      .on("click", function(key) {
          display_mode(MODE_MAP);
          var new_selected_topics_list = selected_topics_list.slice(0, selected_topics_list.indexOf(key) + 1);
          var topics_list = topics_data[key].children.map(function(key) {
              return topics_data[key];
          });
          drawVoronoi(svg, [], d3.range(topics_list.length * 4), opacity_background, IS_BACKGROUND);
          drawVoronoi(svg, new_selected_topics_list, topics_list, opacity_foreground, IS_TOPICS);
      });
}

//  Function that draws a level of knowledge map.
function drawVoronoi(svg, selected_topics_list, topics_list, opacity, type) {
    var voronoi_colorscheme = mashas_colorscheme;

    var N_cells = topics_list.length,
        width = +svg.attr("width"),
        height = +svg.attr("height");

    //  Calculate the number of columns and rows that's enough to contain N_points cells.
    function calculateColsRowsNum(width, height, N_points) {
        var alpha = width / height;
        var num_points_h = Math.ceil(Math.sqrt(N_points / alpha)),
            num_points_w = Math.ceil(N_points / num_points_h);
        return [num_points_w, num_points_h];
    }

    //  Calculate the width and height of a cell.
    function getCellSize(width, height, N_points) {
        var num_points = calculateColsRowsNum(width, height, N_points),
            num_points_w = num_points[0],
            num_points_h = num_points[1];
        var cell_width = Math.floor(width / num_points_w),
            cell_height = Math.floor(height / num_points_h);
        return [cell_width, cell_height];
    }

    //  Calculate the coordinates of cell centers.
    function getPoints(width, height, N_points, random_factor) {
        var num_points = calculateColsRowsNum(width, height, N_points),
            num_points_w = num_points[0],
            num_points_h = num_points[1];
        var cell_size = getCellSize(width, height, N_points),
            cell_width = cell_size[0],
            cell_height = cell_size[1];
        var coordinates_of_points = [];
        for (var i = 0, points_counter = 0, w = Math.floor(cell_width / 2);
            (i < num_points_w) & (points_counter < N_points); i++, w += cell_width) {
            for (var j = 0, h = Math.floor(cell_height / 2);
                (j < num_points_h) && (points_counter < N_points); j++, h += cell_height) {
                    coordinates_of_points.push([
                        w + Math.random() * random_factor * cell_width,
                        h + Math.random() * random_factor * cell_width
                    ]);
                    points_counter++;
            }
        }
        return coordinates_of_points;
    }

    //  Coordinates of cell centers.
    var points = getPoints(width, height, N_cells, random_factor);

    var voronoi = d3.voronoi().extent([
        [-1, -1],
        [width + 1, height + 1]
    ]);

    if (type == IS_BACKGROUND) {
        var polygon = svg.append("g")
            .attr("class", "polygons")
            .selectAll("path")
            .data(d3.zip(topics_list, voronoi.polygons(points)))
            .enter().append("path")
            .call(redrawPolygon);
    }

    if (type == IS_TOPICS) {
        //  Generate cells.
        var polygon = svg.append("g")
            .attr("class", "polygons")
            .selectAll("path")
            .data(d3.zip(topics_list,voronoi.polygons(points)))
            .enter().append("path")
            .on("click", on_click_cell_topic)
            .call(redrawPolygon);
        //  Generate a list of chosen topics on a navigation bar.
        updateChosenTopicsList(selected_topics_list, svg);

        var y_margin_between_topic_words = 20;
        for (var i = 0; i < 4; i++) {
            drawSingleTitle(svg, topics_list,
                            i * y_margin_between_topic_words,
                            topics_list.map(function(topic) {
                                return topic.top_words[i];
                            }),
                            on_click_cell_topic);
        }

        //  Function that calls when a cell or a topic is clicked.
        function on_click_cell_topic() {
            var topic = this.__data__[0];
            //  Get all children of this cell.
            var topics_list = topic.children.map(function(key) {
                return topics_data[key]
            });

            //  Append the chosen topic to the list that will be displayed on the navigation bar.
            selected_topics_list.push(topic.key);
            if (!topic.is_last_level) {
                drawVoronoi(svg, [], d3.range(topic.children.length * 4), opacity_background, IS_BACKGROUND);
                drawVoronoi(svg, selected_topics_list, topics_list, opacity_foreground, IS_TOPICS);
            } else {
                updateChosenTopicsList(selected_topics_list, svg);
                $.ajax({url: "http://localhost:3000/get-documents?topic_id=" + topic.key,
                        success: function(result) {
                            drawVoronoi(svg, chosen_topics_list, result, opacity_background, IS_DOCS);
                       }});
            }
        }
    }

    if (type == IS_DOCS) {
        //  Generate cells.
        var polygon = svg.append("g")
            .attr("class", "polygons")
            .selectAll("path")
            .data(d3.zip(topics_list, voronoi.polygons(points)))
            .enter().append("path")
            .on("click", function (data) { onclickDocumentCell(data[0]); })
            .call(redrawPolygon);

        drawSingleTitle(svg, topics_list, 0, topics_list.map(function(doc) {
            return doc.doc_id
        }), function (data) { onclickDocumentCell(data[0]) });
    }

    //  Draw titles for polygons.
    function drawSingleTitle(svg, data, shift, titles, on_click_listener) {
        var titles = svg.append("g")
            .attr("class", "titles")
            .selectAll("text")
            //  Data for a cell title is 5-tuple:
            .data(d3.zip(
                data,   //  The topic info (json element).
                points, //  The coordinate a cell center.
                d3.range(N_cells).map(function(x) {
                    return shift;
                }),     // The y-shift from a cell center for this title.
                titles  // The number of displayed word from top_words array.
            ))
            .enter().append("text")
            .on("click", on_click_listener)
            .call(redrawTitle);
    }

    //  Function that calls right after cells creation.
    //  Do some routines to finalize the appearance of cells (colors, opacity etc).
    function redrawPolygon(polygon) {
        polygon
            .attr("fill", function(d) {
                var len = Object.keys(voronoi_colorscheme).length,
                    idx = Math.floor(Math.random() * 100000) % len;
                return voronoi_colorscheme[idx];
            })
            .attr("opacity", opacity)
            .attr("d", function(d) {
                return d[1] ? "M" + d[1].join("L") + "Z" : null;
            });
    }

    //  Function that calls right after cells creation.
    //  Do some routines to finalize the appearance of titles (coordinates, text etc).
    function redrawTitle(title) {
        var cell_size = getCellSize(width, height, N_cells),
            cell_width = cell_size[0],
            cell_height = cell_size[1];
        title
            .text(function(d) { return d[3]; })
            .attr("x", function(d) {
                return Math.floor(d[1][0]) - Math.floor((1 - 2 * random_factor) * cell_width * 0.5);
            })
            .attr("y", function(d) {
                return Math.floor(d[1][1]) - Math.floor((1 - 2 * random_factor) * cell_height * 0.5) + d[2];
            });
    }
}

function display_recommendations(doc, recommendations_data) {
    var recommendations_container = d3.select(document.getElementById("recommendations_container"));

    var recommendation_blocks = recommendations_container.append("ui")
        .attr("class", "thumbnails")
        .selectAll("li").data(recommendations_data).enter()
        .append("li").attr("class", "span10")
        .append("a").attr("class", "thumbnail");

    recommendation_blocks.on("click", onclickDocumentCell);
    recommendation_blocks.append("h6")
        .attr("class", "recommendation_title")
        .text(function(doc) {
            return doc.title;
        });
    recommendation_blocks.append("p")
        .attr("class", "recommendation_text")
        .text(function(doc) {
            return doc.markdown.split(".").slice(0, 1).join(".") + "…";
        });
}

function display_document(doc) {
    var document_container = d3.select(document.getElementById("document_container"));
    var doc_text = doc.markdown.replace(new RegExp("\n+", "g"), "<br><br>");
    document_container.append("h1")
        .attr("align", "center")
        .attr("class", "document_title")
        .text(doc.title);
    document_container.append("p")
        .attr("class", "document_text")
        .html(doc_text);
}

function onclickDocumentCell(doc) {
    display_mode(MODE_DOCS);
    display_document(doc);
    $.ajax({url: "http://localhost:3000/get-recommendations?doc_id=" + doc.doc_id.split("_")[1],
            success: function(result) {
                display_recommendations(doc, result);
           }});
}
