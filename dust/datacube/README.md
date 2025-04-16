# **DustStat DataCube**
A flexible **n-dimensional data cube** implementation in Python for **storing, modifying, iterating, and aggregating** structured and numeric data.

### **Key Features**
- **Fixed & dynamic category-based axes** (categories expand automatically).  
- **Supports numeric & structured (dictionary) data storage.**  
- **Aggregation with flexible filtering (by axis, categories, or custom function).**  
- **Cursor-based access for efficient data updates & retrieval.**  
- **Data iteration with sorting, filtering, and callbacks (`visit()`).**  
- **Serialization & deserialization (`to_dict`, `from_dict`).**  

---

## 🛠 **Main Components**
### **1️⃣ DustStatAxisConst**  
Defines an **axis** in the data cube. Axes automatically expand as new categories are added via `set_coordinate()`.  

```python
from dust.datacube.datacube import DustStatAxisConst

axis = DustStatAxisConst("Department")
print(axis.categories())  # Output: []
```

---

### **2️⃣ DustStatDataCubeNumeric (For Numeric Data)**
- Stores **integer/float** values.  
- Supports **summation, incremental updates, and aggregation**.  

#### **Example: Storing Employee Salaries by Department and Year**
```python
from dust.datacube.datacube import DustStatDataCubeNumeric, DustStatAxisConst

# Define axes
cube = DustStatDataCubeNumeric("Salaries", [
    DustStatAxisConst("Year"),
    DustStatAxisConst("Department")
])

cursor = cube.Cursor(cube)

# Set salary data
cursor.set_coordinate("2023", cube.get_axis_by_name("Year"))
cursor.set_coordinate("HR", cube.get_axis_by_name("Department"))
cursor.set_value(50000)

cursor.set_coordinate("2023", cube.get_axis_by_name("Year"))
cursor.set_coordinate("IT", cube.get_axis_by_name("Department"))
cursor.set_value(70000)

cursor.set_coordinate("2024", cube.get_axis_by_name("Year"))
cursor.set_coordinate("HR", cube.get_axis_by_name("Department"))
cursor.increment_value_with(10000)  # HR department gets a raise

# Retrieve Data
cursor.set_coordinate("2023", cube.get_axis_by_name("HR"))
print(cursor.value())  # Output: 50000

# Perform Aggregation
print(cube.aggregate(operation="sum"))  # Total salaries across all departments & years
```

---

### **3️⃣ DustStatDataCubeStructured (For Dictionary-Based Data)**
- Stores **structured (dictionary) values** at each coordinate.  
- Useful for tracking **metadata** instead of just numbers.  

#### **Example: Storing Employee Details**
```python
from dust.datacube.datacube import DustStatDataCubeStructured, DustStatAxisConst

# Define axes
cube = DustStatDataCubeStructured("Employees", [
    DustStatAxisConst("Year"),
    DustStatAxisConst("Department")
])

cursor = cube.Cursor(cube)

# Store structured employee data
cursor.set_coordinate("2023", cube.get_axis_by_name("Year"))
cursor.set_coordinate("HR", cube.get_axis_by_name("Department"))
cursor.set_value({"employees": 10, "budget": 200000})

cursor.set_coordinate("2023", cube.get_axis_by_name("IT"))
cursor.set_coordinate("IT", cube.get_axis_by_name("Department"))
cursor.set_value({"employees": 25, "budget": 500000})

print(cursor.value())  
# Output: {'employees': 25, 'budget': 500000}
```

---

## 🔍 **Aggregation & Filtering**
The `aggregate()` function allows **powerful filtering**:

1️⃣ **Filter by Axis & Categories**  
```python
result = cube.aggregate(
    operation="sum",
    filters={"Year": ["2023"], "Department": ["HR"]}
)
```
- **Includes only specified categories** within selected axes.  
- **Ignores other axes (treats them as wildcards).**  

2️⃣ **Filter via Custom Function**  
```python
def custom_filter(coords):
    return coords[0] == "2023" and coords[1].startswith("I")

result = cube.aggregate(operation="sum", filter_fn=custom_filter)
```
- **More advanced filtering logic**.  
- **Custom coordinate-based selection**.  

---

## 🔄 **Visiting Data Locations (`visit()`)**
The `visit()` method **allows iterating over data** in a structured way, supporting:
- **Axis order customization** (`axis_order=["Year", "Department"]`).
- **Sorting within axes** (`sort_order={"Year": SortOrder.DESCENDING}`).
- **Filtering on categories or using a custom function.**
- **Applying a callback function while iterating.**
- **Returning a generator for memory-efficient iteration.**

---

### **1️⃣ Basic Iteration**
Iterate over all stored data in **natural order**.
```python
for coords, value in cube.visit():
    print(f"{coords}: {value}")
```

---

### **2️⃣ Filtering by Axis & Categories**
```python
for coords, value in cube.visit(filters={"Department": ["IT", "HR"]}):
    print(f"{coords}: {value}")
```
- Visits **only IT and HR departments**.

---

### **3️⃣ Sorting & Custom Axis Order**
```python
from dust.datacube.datacube import SortOrder

for coords, value in cube.visit(
    axis_order=["Year", "Department"],
    sort_order={"Year": SortOrder.DESCENDING}  # Default is ASCENDING for all others
):
    print(f"{coords}: {value}")
```
- Visits **latest years first**, then departments.
- **Unspecified axes remain in natural order**.

---

### **4️⃣ Filtering via Custom Function**
```python
def custom_filter(coords):
    return coords[0] == "2023" and coords[1].startswith("I")  # Year is 2023, Department starts with "I"

for coords, value in cube.visit(filter_fn=custom_filter):
    print(f"{coords}: {value}")
```
- Only includes **entries from 2023 where the department starts with "I"**.

---

### **5️⃣ Filtering on Data Values**
```python
for coords, value in cube.visit(value_filter=lambda v: v["budget"] > 300000):
    print(f"{coords}: {value}")
```
- Visits **only locations where budget > 300K**.

---

### **6️⃣ Using a Callback Function**
```python
def process_entry(coords, value):
    print(f"{coords}: {value}")

cube.visit(callback=process_entry)
```
- **Processes each entry in real-time** instead of storing results.

---

## 📦 **Serialization (`to_dict`, `from_dict`)**
### **Save Cube to JSON**
```python
import json

cube_data = cube.to_dict()
with open("cube.json", "w") as f:
    json.dump(cube_data, f)
```

### **Load Cube from JSON**
```python
with open("cube.json", "r") as f:
    cube_data = json.load(f)

loaded_cube = DustStatDataCubeNumeric.from_dict(cube_data)
```