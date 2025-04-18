# **DustStat DataCube & ChartUI**

A flexible system for **structured, multidimensional data analysis and visualization** using custom-built data cubes and chart generation logic. Tailored for developers who need to collect, structure, and display rich metrics in a way that’s easy to serialize, iterate, and visualize.

---

## 🧱 `datacube.py` – Structured N-Dimensional Data Cubes

The `datacube.py` module provides:
- An extensible system for defining **axes** (dimensions) and their **categories**
- Tools for creating cubes with structured or numeric values
- Built-in support for **iteration**, **sorting**, **filtering**, and **category metadata**
- A `visit()` method that allows fine-grained data access

---

### ✅ Example: Tracking Time Off

Use a cube to track different types of employee absences over time.

```python
from datacube import DustStatDataCubeStructured, DustStatAxisConst

cube = DustStatDataCubeStructured("TimeOff", [
    DustStatAxisConst("Employee"),
    DustStatAxisConst("Year"),
    DustStatAxisConst("Type")
])

cursor = DustStatDataCubeStructured.Cursor(cube)

# Populate cube with structured values
cursor.set_coordinate("Alice", cube.get_axis_by_name("Employee"))
cursor.set_coordinate("2024", cube.get_axis_by_name("Year"))
cursor.set_coordinate("Vacation", cube.get_axis_by_name("Type"))
cursor.set_value({"days": 12})

cursor.set_coordinate("Alice", cube.get_axis_by_name("Type"))
cursor.set_coordinate("Sick", cube.get_axis_by_name("Type"))
cursor.set_value({"days": 3})

cursor.set_coordinate("Bob", cube.get_axis_by_name("Type"))
cursor.set_coordinate("Training", cube.get_axis_by_name("Type"))
cursor.set_value({"days": 5})

cursor.set_coordinate("Bob", cube.get_axis_by_name("Type"))
cursor.set_coordinate("Remote", cube.get_axis_by_name("Type"))
cursor.set_value({"days": 20})
```

---

### 🔁 Visit, Sort & Filter

```python
# Iterate in default order
for coords, value in cube.visit():
    print(coords, value)

# Filter only Sick leave
for coords, value in cube.visit(filters={"Type": ["Sick"]}):
    print("Sick leave:", coords, value)

# Order by Employee, Year, then Type
from datacube import SortOrder

for coords, value in cube.visit(
    axis_order=["Employee", "Year", "Type"],
    sort_order={"Employee": SortOrder.ASCENDING, "Year": SortOrder.DESCENDING, "Type": SortOrder.ASCENDING}
):
    print("Sorted:", coords, value)
```

---

## 📊 `chartui.py` – Chart Data Generator (for Chart.js)

The `chartui.py` module provides:
- A chart type registry (`bar`, `line`, etc.)
- Declarative configs for how data is grouped
- Output as Chart.js-compatible JSON
- Support for stacking, annotations, filtering, and series splitting

---

### ✅ Example: Days Off per Employee (Grouped by Type)

```python
from chartui import generate_chart_data

chart_config = {
    "type": "bar",
    "visit": lambda cube: cube.visit(),
    "x": lambda coords, _: coords[0],  # Employee
    "stack_by": lambda coords, _: coords[2],  # Type (Vacation, Sick, etc.)
    "count": lambda _, value: value["days"],
    "colors": {
        "Vacation": "#4CAF50",
        "Sick": "#F44336",
        "Training": "#2196F3",
        "Remote": "#FF9800"
    },
    "label_metric": lambda coords, value: (coords[2], value["days"]),
    "label_formatter": lambda items: f"{sum(v[1] for v in items)} days"
}

chart = generate_chart_data(cube, chart_config)
```

---

### 🧠 Advanced Filtering and Axis Ordering in Charts

You can use the full power of the cube’s `.visit()` method within chart configs:

```python
chart_config = {
    "type": "bar",
    "visit": lambda cube: cube.visit(
        axis_order=["Employee", "Year", "Type"],
        sort_order={
            "Employee": SortOrder.ASCENDING,
            "Year": SortOrder.DESCENDING,
            "Type": SortOrder.ASCENDING
        },
        filters={"Type": ["Vacation", "Remote"]}
    ),
    "x": lambda coords, _: f"{coords[0]} ({coords[1]})",  # Employee (Year)
    "stack_by": lambda coords, _: coords[2],  # Type
    "count": lambda _, value: value["days"],
    "colors": {"Vacation": "#4CAF50", "Remote": "#FF9800"},
}
```

---

## 🔒 Metadata Support

Each axis and value can have rich metadata attached:

```python
employee_axis = cube.get_axis_by_name("Employee")
employee_axis.set_metadata("Alice", "team", "Engineering")
employee_axis.set_metadata("Bob", "team", "Sales")

print(employee_axis.get_metadata("Bob", "team"))  # Sales
```

---

## 📦 Serialization & Interoperability

```python
import json

with open("cube.json", "w") as f:
    json.dump(cube.to_dict(), f)

# Later
from datacube import DustStatDataCubeStructured

with open("cube.json") as f:
    cube = DustStatDataCubeStructured.from_dict(json.load(f))
```

---

## 🧠 Designed for Developers

- Modular, flexible, and JSON/YAML serializable
- Can be plugged into async pipelines, GCS storage, dashboards, or CLI tools
- Easily extended with new chart types or cube features