"""
DustStat: A multi-dimensional data cube implementation in Python.

This module provides a way to store and manipulate values in an n-dimensional space,
where each dimension is defined by an axis. Data is stored in a dictionary, indexed
by coordinates (tuples of indices corresponding to axis categories). The cube supports
retrieving, setting, and incrementing values at specific coordinates.
"""

import json
import yaml
import hashlib
from collections import defaultdict
from typing import List, Dict, Tuple, Union, Optional, Callable, Generator
from enum import Enum
from abc import ABC, abstractmethod

class AggregationOperation(Enum):
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"

class SortOrder(Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"

class DustStatCubeType(Enum):
    NUMERIC = "numeric"
    STRUCTURED = "structured"

class DustStatAxis(ABC):
    """Base class for an axis in the data cube."""
    
    def __init__(self, name: str):
        self.name: str = name
        self.metadata: Dict[str, Dict[str, Union[str, int, float]]] = {}

    @abstractmethod
    def categories(self) -> List[str]:
        """Must be implemented in derived classes to return the categories of the axis."""
        pass

    def set_metadata(self, category: str, key: str, value: Union[str, int, float]) -> None:
        """Stores metadata for a given category in this axis."""
        if category not in self.metadata:
            self.metadata[category] = {}
        self.metadata[category][key] = value

    def get_metadata(self, category: str, key: str) -> Optional[Union[str, int, float]]:
        """Retrieves metadata for a given category."""
        return self.metadata.get(category, {}).get(key, None)


class DustStatAxisConst(DustStatAxis):
    def __init__(self, name: str, categories: Optional[List[str]] = None):
        super().__init__(name)
        self._categories: List[str] = categories if categories else []
        self._category_to_index: Dict[str, int] = {cat: i for i, cat in enumerate(self._categories)}

    def categories(self) -> List[str]:
        """Returns the current list of categories."""
        return self._categories

    def add_category(self, category: str) -> None:
        """Dynamically adds a category if it does not already exist and assigns it an index."""
        if category not in self._category_to_index:
            self._category_to_index[category] = len(self._categories)
            self._categories.append(category)

    def set_categories(self, categories: List[str]) -> None:
        """Sets the categories for the axis and rebuilds the index mapping."""
        self._categories = list(categories)
        self._category_to_index = {cat: idx for idx, cat in enumerate(self._categories)}

    def get_index(self, category: str) -> int:
        """Returns the index of a category, adding it if it doesn't exist."""
        if category not in self._category_to_index:
            self.add_category(category)
        return self._category_to_index[category]

    def get_category(self, index: int) -> str:
        """Returns the category name corresponding to an index."""
        return self._categories[index]

    def to_dict(self) -> Dict:
        """Serializes the axis to a dictionary."""
        return {"name": self.name, "categories": self._categories, "metadata": self.metadata}
    
    @staticmethod
    def from_dict(data: Dict) -> "DustStatAxisConst":
        """Deserializes a DustStatAxisConst from a dictionary."""
        axis = DustStatAxisConst(name=data["name"], categories=data.get("categories", []))
        axis.metadata = data.get("metadata", {})
        axis._category_to_index = {cat: i for i, cat in enumerate(axis._categories)}  # Rebuild index map
        return axis

    def to_yaml(self) -> str:
        """Returns a YAML representation of the axis with category names instead of index keys."""
        formatted_categories = [
            {"cat": cat, "value": self.metadata.get(cat, {}) or {}}
            for cat in self._categories
        ]

        return yaml.dump({
            "name": self.name,
            "categories": formatted_categories,  # Use list format
        }, sort_keys=False)
    
    @staticmethod
    def from_yaml(yaml_str: str) -> "DustStatAxisConst":
        """Deserializes an axis from a YAML string and restores category metadata."""
        data = yaml.safe_load(yaml_str)

        axis = DustStatAxisConst(name=data["name"], categories=[entry["cat"] for entry in data["categories"]])

        # Restore metadata from the new list format
        axis.metadata = {entry["cat"]: entry["value"] for entry in data["categories"] if entry["value"]}

        return axis

class DustStatDataCube(ABC):
    """Abstract base class for a data cube."""

    def __init__(self, name: str, axes: List[DustStatAxisConst], cube_type: DustStatCubeType):
        self.name: str = name
        self._axes: List[DustStatAxisConst] = axes
        self.values: Dict[Tuple[str, ...], Union[int, float, Dict]] = {}
        self.metadata: Dict[str, Union[str, int, float]] = {}
        self.type = cube_type

    def axes(self) -> List[DustStatAxisConst]:
        """Returns the list of axes in the cube."""
        return self._axes

    def set_metadata(self, key: str, value: Union[str, int, float]) -> None:
        """Stores metadata at the cube level."""
        self.metadata[key] = value

    def get_metadata(self, key: str) -> Optional[Union[str, int, float]]:
        """Retrieves metadata at the cube level."""
        return self.metadata.get(key)
    
    def has_value(self, coordinates: Tuple[str, ...]) -> bool:
        """Checks if a value exists at the given coordinates using index-based lookup."""
        try:
            index_tuple = tuple(axis.get_index(cat) for axis, cat in zip(self._axes, coordinates))
            return index_tuple in self.values  # ✅ Use index-based keys
        except ValueError:
            return False  # Category not found in axis, meaning it does not exist in the cube

    def delete_value(self, coordinates: Tuple[str, ...]) -> None:
        """Removes a value from the data cube using category names by converting to index-based keys."""
        index_coords = tuple(axis.get_index(cat) for axis, cat in zip(self._axes, coordinates))
        if index_coords in self.values:
            del self.values[index_coords]

    def to_dict(self, transfer_value_keys = False) -> Dict:
        """Serializes the data cube using index-based storage."""
        if transfer_value_keys:
            return {
                "name": self.name,
                "axes": [axis.to_dict() for axis in self._axes],
                "values": {json.dumps([axis.get_category(idx) for axis, idx in zip(self._axes, key)]): value for key, value in self.values.items()},
                "type": self.type.value,
                "metadata": self.metadata,
            }
        else:
            return {
                "name": self.name,
                "axes": [axis.to_dict() for axis in self._axes],
                "values": {json.dumps(key): value for key, value in self.values.items()},
                "type": self.type.value,
                "metadata": self.metadata,
            }

    def iterate_values(self):
        """Generator that yields (category_names, value) pairs."""
        for coords, value in self.values.items():
            category_names = tuple(axis.get_category(idx) for axis, idx in zip(self._axes, coords))
            yield category_names, value

    def remove_categories(self, categories_per_axis: Dict[DustStatAxis, List[str]]) -> None:
        """
        Removes specified categories from each axis, updates metadata, and reindexes values.

        Args:
            categories_per_axis (Dict[DustStatAxis, List[str]]): 
                A dictionary where keys are axes and values are lists of categories to remove.
        """
        # Step 1: Backup the old category-to-index mapping
        old_category_to_index = {
            axis: {idx: cat for idx, cat in enumerate(axis.categories())} 
            for axis in self._axes
        }

        # Step 2: Remove specified categories from each axis and rebuild mappings
        new_index_mapping_per_axis = {}
        for axis, categories_to_remove in categories_per_axis.items():
            # Keep only categories that are not being removed
            remaining_categories = [cat for cat in axis.categories() if cat not in categories_to_remove]

            # Rebuild category-to-index mapping
            new_index_mapping_per_axis[axis] = {cat: idx for idx, cat in enumerate(remaining_categories)}

            # Remove metadata for deleted categories BEFORE updating categories
            for cat in categories_to_remove:
                if cat in axis.metadata:
                    del axis.metadata[cat]

            # Apply new categories to the axis
            axis.set_categories(remaining_categories)

        # Step 3: Reindex stored values
        new_values = {}
        for old_coords, value in self.values.items():
            new_coords = []
            for idx, axis in enumerate(self._axes):
                old_cat = old_category_to_index[axis][old_coords[idx]]  # Get category name
                if old_cat not in new_index_mapping_per_axis[axis]:  # Skip removed categories
                    break
                new_coords.append(new_index_mapping_per_axis[axis][old_cat])  # Get new index
            else:
                new_values[tuple(new_coords)] = value  # Store only if all categories are valid

        # Step 4: Replace values with updated reindexed data
        self.values = new_values

    def compute_checksum(self, dump_path=None) -> str:
        """Generates a stable SHA-256 checksum by replacing indexes with category names before hashing."""

        def sorted_json(obj):
            """Recursively sorts lists and dictionaries for stable hashing."""
            if isinstance(obj, dict):
                return {k: sorted_json(v) for k, v in sorted(obj.items())}
            elif isinstance(obj, list):
                return sorted((sorted_json(item) for item in obj), key=json.dumps)  # Sort using JSON for stability
            elif isinstance(obj, tuple):
                return tuple(sorted_json(list(obj)))
            else:
                return obj

        # Convert cube to dictionary (uses index-based coords)
        cube_dict = self.to_dict(transfer_value_keys=True)

        # Remove checksum before hashing
        cube_dict["metadata"].pop("checksum", None)

        # Sort everything before hashing
        sorted_cube_dict = sorted_json(cube_dict)

        if dump_path:
            # Write debug file to verify output before hashing
            with open(dump_path, "w", encoding="utf-8") as f:
                json.dump(sorted_cube_dict, f, indent=4, sort_keys=True)

        # Generate checksum
        chechsum = hashlib.sha256(json.dumps(sorted_cube_dict, sort_keys=True).encode()).hexdigest()
        self.set_metadata("checksum", chechsum)

        return chechsum

    @staticmethod
    def from_dict(data: Dict) -> "DustStatDataCube":
        """Deserializes a data cube from a dictionary."""
        axes = [DustStatAxisConst.from_dict(axis_data) for axis_data in data["axes"]]
        cube_type = DustStatCubeType(data["type"])
        
        # Determine the type of cube to instantiate
        if cube_type == DustStatCubeType.NUMERIC:
            cube = DustStatDataCubeNumeric(data["name"], axes)
        else:
            cube = DustStatDataCubeStructured(data["name"], axes)

        # Convert list keys back to tuples
        cube.values = {tuple(json.loads(key)): value for key, value in data["values"].items()}
        
        return cube
    
    def to_yaml(self) -> str:
        """Returns a YAML representation of the data cube with category names for debugging."""
        formatted_values = [
            {
                "coord": {axis.name: axis.get_category(idx) for axis, idx in zip(self._axes, key)},
                "value": value
            }
            for key, value in self.values.items()
        ]

        formatted_axes = [
            {
                "name": axis.name,
                "categories": [{"cat": category, "value": axis.metadata.get(category, {}) or {}} for category in axis.categories()]
            }
            for axis in self._axes
        ]

        return yaml.safe_dump({
            "name": self.name,
            "axes": formatted_axes,
            "values": formatted_values,
            "type": self.type.value,
            "metadata": self.metadata if self.metadata else {},
        }, sort_keys=False, default_style=None)

    @staticmethod
    def from_yaml(yaml_str: str) -> "DustStatDataCube":
        """Deserializes a data cube from a YAML string, restoring category names safely."""
        data = yaml.safe_load(yaml_str)

        # Rebuild axes from YAML (handling {cat, value} format)
        axes = [
            DustStatAxisConst(
                name=axis_data["name"],
                categories=[entry["cat"] for entry in axis_data["categories"]]
            ) for axis_data in data["axes"]
        ]

        # Restore metadata for each axis
        for axis, axis_data in zip(axes, data["axes"]):
            axis.metadata = {entry["cat"]: entry.get("value", {}) for entry in axis_data["categories"] if entry.get("value")}

        # Determine cube type
        cube_type = DustStatCubeType(data["type"])
        cube = (
            DustStatDataCubeNumeric(data["name"], axes)
            if cube_type == DustStatCubeType.NUMERIC
            else DustStatDataCubeStructured(data["name"], axes)
        )

        # Convert category names back to index-based storage
        for entry in data["values"]:
            coord_dict = entry["coord"]
            value = entry["value"]

            # Convert category names to index tuple
            coord_tuple = tuple(axis.get_index(coord_dict[axis.name]) for axis in axes)

            cube.values[coord_tuple] = value  # Restore indexed value

        # ✅ Ensure metadata is restored only when non-empty
        cube.metadata = data.get("metadata", {}) or {}

        return cube


class DustStatDataCubeNumeric(DustStatDataCube):
    """Data cube that stores and sums numeric values."""

    def __init__(self, name: str, axes: List[DustStatAxisConst]):
        super().__init__(name, axes, DustStatCubeType.NUMERIC)

    def aggregate(
        self,
        operation: AggregationOperation,
        filters: Optional[Dict[str, List[str]]] = None,
        filter_fn: Optional[Callable[[Tuple[str, ...]], bool]] = None
    ) -> float:
        """
        Performs aggregation (sum, avg, min, max) with optional filtering.

        Args:
            operation (AggregationOperation): The aggregation operation ("sum", "avg", "min", "max").
            filters (Optional[Dict[str, List[str]]]): A dictionary specifying axes and the categories to include.
            filter_fn (Optional[Callable[[Tuple[str, ...]], bool]]): A custom function to filter coordinates.

        Returns:
            float: The aggregated result.

        Raises:
            ValueError: If an invalid aggregation operation is given.
        """
        # Precompute axis indices for faster lookups (avoids recomputing them inside the loop)
        axis_indices = {axis.name: i for i, axis in enumerate(self._axes)}

        selected_values = [
            value for coords, value in self.values.items()  # Iterate over all stored values
            if (
                # Check if filters exist and apply them
                (not filters or all(
                    coords[axis_indices[axis_name]] in allowed_categories  # Check if the coordinate matches allowed categories
                    for axis_name, allowed_categories in filters.items()  # Iterate over all filters
                    if axis_name in axis_indices  # Ensure the axis exists in the cube before accessing its index
                ))
                and (not filter_fn or filter_fn(coords))  # Apply custom filter function (if provided)
            )
        ]

        # Return aggregated result
        if not selected_values:
            return None  # Return None if no matching data

        match operation:
            case AggregationOperation.SUM:
                return sum(selected_values)
            case AggregationOperation.AVG:
                return sum(selected_values) / len(selected_values)
            case AggregationOperation.MIN:
                return min(selected_values)
            case AggregationOperation.MAX:
                return max(selected_values)
            case _:
                raise ValueError(f"Unknown aggregation operation: {operation}")

    class Cursor:
        """Cursor for setting and retrieving values from a numeric data cube."""

        def __init__(self, cube: "DustStatDataCubeNumeric"):
            self.cube = cube
            self.coords: List[Optional[str]] = [None] * len(cube.axes())

        def __get_index_tuple(self) -> Tuple[int, ...]:
            return tuple(
                axis.get_index(self.coords[i]) if self.coords[i] is not None else -1
                for i, axis in enumerate(self.cube.axes())
            )

        def set_coordinate(self, category: str, axis: DustStatAxisConst) -> None:
            """Sets a coordinate value for a given axis, dynamically adding new categories if needed."""
            axis.add_category(category)
            idx_axis = self.cube.axes().index(axis)
            self.coords[idx_axis] = category

        def clear_coordinates(self) -> None:
            """Resets the cursor position."""
            self.coords = [None] * len(self.cube.axes())

        def value(self) -> Optional[float]:
            """Retrieves the value at the current location."""
            return self.cube.values.get(self.__get_index_tuple(), 0)

        def set_value(self, value: float) -> None:
            """Sets a numeric value at the current location."""
            self.cube.values[self.__get_index_tuple()] = value

        def increment_value_with(self, value: float) -> None:
            """Increments the numeric value at the current location."""
            current_value = self.value() or 0
            self.set_value(current_value + value)

        def has_value(self) -> bool:
            """Returns True if a value has been set at the current cursor location (excluding explicit None)."""
            index_tuple = self.__get_index_tuple()
            return index_tuple in self.cube.values and self.cube.values[index_tuple] is not None



class DustStatDataCubeStructured(DustStatDataCube):
    """Data cube that stores structured (dictionary) values."""

    def __init__(self, name: str, axes: List[DustStatAxisConst]):
        super().__init__(name, axes, DustStatCubeType.STRUCTURED)

    def visit(
        self,
        axis_order: Optional[List[str]] = None,
        sort_order: Optional[Dict[str, SortOrder]] = None,
        filters: Optional[Dict[str, List[str]]] = None,
        filter_fn: Optional[Callable[[Tuple[str, ...]], bool]] = None,
        value_filter: Optional[Callable[[Dict], bool]] = None,
        callback: Optional[Callable[[Tuple[str, ...], Dict], None]] = None
    ) -> Generator[Tuple[Tuple[str, ...], Dict], None, None]:
        """
        Iterates over the structured cube's data locations in a flexible way.

        Args:
            axis_order (Optional[List[str]]): Order in which axes should be visited.
            sort_order (Optional[Dict[str, SortOrder]]): Sorting preference per axis.
            filters (Optional[Dict[str, List[str]]]): Filter categories per axis.
            filter_fn (Optional[Callable[[Tuple[str, ...]], bool]]): Custom filter for coordinates.
            value_filter (Optional[Callable[[Dict], bool]]): Custom filter for data values.
            callback (Optional[Callable[[Tuple[str, ...], Dict], None]]): Function to process each entry.

        Yields:
            Generator[Tuple[Tuple[str, ...], Dict]]: Coordinates and values that match the filters.
        """

        # Determine axis order (default: cube's natural order)
        if axis_order:
            ordered_axes = [axis for axis in self._axes if axis.name in axis_order]
            ordered_axes += [axis for axis in self._axes if axis.name not in axis_order]  # Preserve natural order for unspecified axes
        else:
            ordered_axes = self._axes[:]  # Use natural order if no custom order is provided

        # Sorting function for categories within an axis
        def get_sorted_categories(axis: DustStatAxisConst):
            categories = axis.categories()
            
            order = sort_order[axis.name] if sort_order and axis.name in sort_order else SortOrder.ASCENDING
            is_descending = order == SortOrder.DESCENDING

            return sorted(categories, reverse=is_descending)

        # Map the ordered axes to their positions in the original cube
        axis_position_map = {axis.name: i for i, axis in enumerate(self._axes)}

        def traverse(coords: List[str], remaining_axes: List[DustStatAxisConst]):
            if not remaining_axes:  # Base case: all axes set
                # Reconstruct coordinate tuple in the cube's natural axis order
                reordered_coords = [None] * len(self._axes)
                for i, axis in enumerate(ordered_axes):
                    reordered_coords[axis_position_map[axis.name]] = coords[i]

                coord_tuple = tuple(reordered_coords)  # Ensure correct order for lookup
                value = self.values.get(coord_tuple)  # Lookup in self.values with correct order

                # Apply value filter (if provided)
                if value_filter and (value is None or not value_filter(value)):
                    return

                # Apply coordinate filters
                if filter_fn and not filter_fn(coord_tuple):
                    return

                if callback:
                    callback(coord_tuple, value)

                yield coord_tuple, value
                return

            # Process the next axis in the specified order
            next_axis = remaining_axes[0]
            for category in get_sorted_categories(next_axis):
                # Apply category filters
                if filters and next_axis.name in filters and category not in filters[next_axis.name]:
                    continue

                yield from traverse(coords + [category], remaining_axes[1:])

        # Start traversal
        yield from traverse([], ordered_axes)


    class Cursor:
        """Cursor for setting and retrieving structured values from a data cube."""

        def __init__(self, cube: "DustStatDataCubeStructured"):
            self.cube = cube
            self.coords: List[Optional[str]] = [None] * len(cube.axes())

        def __get_index_tuple(self) -> Tuple[int, ...]:
            return tuple(
                axis.get_index(self.coords[i]) if self.coords[i] is not None else -1
                for i, axis in enumerate(self.cube.axes())
            )

        def set_coordinate(self, category: str, axis: DustStatAxisConst) -> None:
            """Sets a coordinate value for a given axis, dynamically adding new categories if needed."""
            axis.add_category(category)
            idx_axis = self.cube.axes().index(axis)
            self.coords[idx_axis] = category

        def value(self) -> Optional[Dict]:
            """Retrieves the structured value at the current location."""
            return self.cube.values.get(self.__get_index_tuple(), None)

        def set_value(self, value: Dict) -> None:
            """Sets a structured value at the current location."""
            self.cube.values[self.__get_index_tuple()] = value

        def has_value(self) -> bool:
            """Returns True if a value has been set at the current cursor location (excluding explicit None)."""
            coords_tuple = self.__get_index_tuple()
            return coords_tuple in self.cube.values and self.cube.values[coords_tuple] is not None