from collections import defaultdict

# Chart type registry
CHART_HANDLERS = {}

def register_chart_handler(chart_type):
    def decorator(fn):
        CHART_HANDLERS[chart_type] = fn
        return fn
    return decorator

def generate_chart_data(cube, config):
    chart_type = config.get("type")
    if chart_type not in CHART_HANDLERS:
        raise ValueError(f"Unsupported chart type: {chart_type}")
    return CHART_HANDLERS[chart_type](cube, config)


@register_chart_handler("bar")
def generate_bar_chart(cube, config):
    # Extract config callables
    visit_fn = config["visit"]
    x_fn = config["x"]
    count_fn = config["count"]
    filter_fn = config.get("filter", lambda *_: True)
    stack_fn = config.get("stack_by")
    colors = config.get("colors")
    label_metric_fn = config.get("label_metric")
    label_formatter_fn = config.get("label_formatter")

    x_order = config.get("x_order")
    stack_order = config.get("stack_order")

    # Aggregated chart data
    bar_data = defaultdict(lambda: defaultdict(int))
    label_tracker = defaultdict(set)  # To track label metrics per x

    for coords, value in visit_fn(cube):
        if not filter_fn(coords, value):
            continue

        x_key = x_fn(coords, value)
        stack_key = stack_fn(coords, value) if stack_fn else None
        count = count_fn(coords, value)

        # Aggregate count
        if stack_fn:
            bar_data[x_key][stack_key] += count
        else:
            bar_data[x_key] += count

        # Track label metric if provided
        if label_metric_fn:
            label_tracker[x_key].add(label_metric_fn(coords, value))

    # Optional per-bar annotations
    x_labels = x_order or list(bar_data.keys())
    annotations = {
        x: label_formatter_fn(label_tracker[x])
        for x in x_labels
    } if label_metric_fn and label_formatter_fn else {}

    if stack_fn is None:
        # Not a stacked chart, just one dataset
        dataset = {
            "label": config.get("label", "value"),  # optional override
            "data": [],
            "backgroundColor": colors.get(config.get("label", "value"))
        }

        # Prepare ordered labels
        for x in x_labels:
            dataset["data"].append(bar_data[x])  # value is directly int

        return {
            "type": "bar",
            "data": {
                "labels": x_labels,
                "datasets": [dataset],
            },
            "annotations": annotations,
            "options": config.get("options", {})
        }
    else:
        # Prepare ordered labels
        stacks = stack_order or sorted({s for bars in bar_data.values() for s in bars})
        # Prepare datasets
        datasets = []
        for stack in stacks:
            datasets.append({
                "label": stack,
                "data": [bar_data[x].get(stack, 0) for x in x_labels],
                "backgroundColor": colors.get(stack)
            })


        return {
            "type": "bar",
            "data": {
                "labels": x_labels,
                "datasets": datasets,
            },
            "annotations": annotations,
            "options": config.get("options", {})
        }
    
@register_chart_handler("line")
def generate_line_chart(cube, config):
    from collections import defaultdict

    # Required config callbacks
    visit_fn = config["visit"]             # Function returning iterator of (coords, value)
    x_fn = config["x"]                     # Extracts x-axis label (e.g., period)
    y_fn = config["y"]                     # Extracts y-axis value (e.g., count)

    # Optional config callbacks
    filter_fn = config.get("filter", lambda *_: True)  # Optional filter on (coords, value)
    series_fn = config.get("series_by")                # Optional function to split data into series
    label_formatter_fn = config.get("label_formatter") # Optional formatting of collected labels

    # Optional config parameters
    colors = config.get("colors", {})                  # Color per series (dict)
    x_order = config.get("x_order")                    # Optional predefined order of x-axis labels
    series_order = config.get("series_order")          # Optional predefined order of series keys

    DEFAULT_SERIES_KEY = "__default__"

    # Store data points: series_key -> x_key -> y_value
    line_data = defaultdict(lambda: defaultdict(float))

    # Collect label metrics per x_key (for annotation)
    label_tracker = {}

    x_keys_seen = []  # Track x_keys in visit order without duplication 

    # Pass 1: visit cube, aggregate values and collect annotation metrics
    for coords, value in visit_fn(cube):
        if not filter_fn(coords, value):
            continue

        x_key = x_fn(coords, value) 
        y_value = y_fn(coords, value)  # e.g., count

        # Track x_key insertion order (preserve natural iteration order)
        if x_key not in x_keys_seen:
            x_keys_seen.append(x_key)

        series_keys = series_fn(coords, value) if series_fn else DEFAULT_SERIES_KEY

        # Ensure we always work with a list of series keys
        if not isinstance(series_keys, list):
            series_keys = [series_keys]

        for key in series_keys:
            line_data[key][x_key] += y_value

    # Sort axis labels and series keys
    x_labels = x_order or x_keys_seen
    if label_formatter_fn:
        for x_label in x_labels:
            label_tracker[x_label] = label_formatter_fn(x_label)

    series_order_keys = series_order or sorted(line_data.keys())

    # Build annotation labels using formatter function
    annotations = {
        x: label_tracker[x]
        for x in x_labels
    } if label_formatter_fn else {}

    # Build chart.js dataset entries
    datasets = []
    for series in series_order_keys:
        datasets.append({
            "label": None if series == DEFAULT_SERIES_KEY else series,
            "data": [line_data[series].get(x, 0) for x in x_labels],
            "borderColor": colors.get(series, "#000000"),
            "backgroundColor": colors.get(series, "#000000"),
            "fill": True,
            "tension": 0.1  # Smooth out the line slightly
        })

    # Return final chart config for chart.js
    return {
        "type": "line",
        "data": {
            "labels": x_labels,
            "datasets": datasets
        },
        "annotations": annotations,
        "options": config.get("options", {})
    }
