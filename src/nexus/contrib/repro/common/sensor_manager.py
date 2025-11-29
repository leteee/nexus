# src/nexus/contrib/repro/common/sensor_manager.py

import json
from bisect import bisect_left
from typing import List, Dict, Any, Optional, Tuple

class SensorStream:
    """
    Manages and provides time-based access to a single stream of sensor data from a JSONL file.
    It supports data delays and provides efficient time-based queries using multiple strategies.
    """

    def __init__(self, data_path: str, time_offset_ms: float = 0):
        """
        Initializes the stream by loading, parsing, and sorting data from the given file.
        """
        self.data_path = data_path
        self.time_offset_ms = time_offset_ms
        self._data: List[Dict[str, Any]] = []
        self._timestamps: List[float] = []
        self._load_data()

        self._match_strategies = {
            "forward": self._find_forward,
            "backward": self._find_backward,
            "nearest": self._find_nearest,
        }

    def _load_data(self):
        """Loads data from a JSONL file and sorts it by timestamp."""
        temp_data = []
        with open(self.data_path, "r", encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    if "timestamp_ms" not in record:
                        raise ValueError(f"Record in {self.data_path} is missing 'timestamp_ms': {record}")
                    temp_data.append(record)
        
        temp_data.sort(key=lambda x: x["timestamp_ms"])
        
        self._data = temp_data
        self._timestamps = [d["timestamp_ms"] for d in self._data]

    def _find_forward(self, aligned_time_ms: float) -> Optional[int]:
        """Finds the index of the latest data point at or before the given time."""
        i = bisect_left(self._timestamps, aligned_time_ms)
        if i == 0 and self._timestamps[0] > aligned_time_ms:
            return None
        if i > 0 and self._timestamps[i - 1] < aligned_time_ms and self._timestamps[i] == aligned_time_ms:
            return i
        return i - 1

    def _find_backward(self, aligned_time_ms: float) -> Optional[int]:
        """Finds the index of the earliest data point at or after the given time."""
        i = bisect_left(self._timestamps, aligned_time_ms)
        if i == len(self._timestamps):
            return None
        return i

    def _find_nearest(self, aligned_time_ms: float) -> Optional[int]:
        """Finds the index of the data point with the timestamp closest to the given time."""
        i = bisect_left(self._timestamps, aligned_time_ms)
        if i == 0:
            return 0
        if i == len(self._timestamps):
            return i - 1

        # Candidates are at i-1 and i. Compare their distance to the aligned time.
        before = self._timestamps[i - 1]
        after = self._timestamps[i]
        if (aligned_time_ms - before) < (after - aligned_time_ms):
            return i - 1
        else:
            return i

    @property
    def min_timestamp(self) -> Optional[float]:
        """Returns the minimum timestamp in the data, or None if empty."""
        return self._timestamps[0] if self._timestamps else None

    @property
    def max_timestamp(self) -> Optional[float]:
        """Returns the maximum timestamp in the data, or None if empty."""
        return self._timestamps[-1] if self._timestamps else None

    def get_value_at(self, snapshot_time_ms: float, strategy: str = "forward") -> Optional[Dict[str, Any]]:
        """
        Finds the most relevant data point for a given snapshot time using a specified strategy.

        Args:
            snapshot_time_ms: The "world time" for which the snapshot is requested.
            strategy: The matching strategy. One of 'forward' (default), 'backward', or 'nearest'.

        Returns:
            A dictionary containing the matched data plus `snapshot_time_ms` and
            `aligned_time_ms`, or None if no suitable data is found.
        """
        if not self._data:
            return None

        # 1. Get the strategy implementation from the dispatch table
        strategy_fn = self._match_strategies.get(strategy)
        if not strategy_fn:
            raise NotImplementedError(f"Strategy '{strategy}' is not implemented. Available strategies are: {list(self._match_strategies.keys())}")

        # 2. Calculate the aligned time for lookup
        aligned_time_ms = snapshot_time_ms - self.time_offset_ms

        # 3. Find the index of the best match using the chosen strategy
        matched_index = strategy_fn(aligned_time_ms)

        if matched_index is None:
            return None

        # 4. Get the matched data and augment it with traceability info
        matched_data = self._data[matched_index]
        result = matched_data.copy()
        result['snapshot_time_ms'] = snapshot_time_ms
        result['aligned_time_ms'] = aligned_time_ms
        return result

    def __len__(self):
        return len(self._data)


class SensorDataManager:
    """
    A central manager for multiple SensorStream objects.
    
    It allows registering sensors with individual time offsets and provides time-range queries
    and synchronized state snapshots at any given point in time.
    """

    def __init__(self):
        self._sensors: Dict[str, SensorStream] = {}

    def register_sensor(self, name: str, data_path: str, time_offset_ms: float = 0):
        """
        Registers a new sensor stream with the manager.

        Args:
            name: A unique name for the sensor (e.g., 'gps', 'imu_1').
            data_path: The path to the sensor's JSONL data file.
            time_offset_ms: The inherent time offset of this sensor in milliseconds.
        """
        if name in self._sensors:
            raise ValueError(f"Sensor with name '{name}' is already registered.")
        
        self._sensors[name] = SensorStream(data_path, time_offset_ms=time_offset_ms)

    def get_time_range(self, sensor_name: Optional[str] = None) -> Optional[Tuple[float, float]]:
        """
        Gets the (min_timestamp, max_timestamp) for a specific sensor or for all sensors globally.

        - If `sensor_name` is provided, it returns the time range for that sensor.
        - If `sensor_name` is None (default), it returns the overall time range across all sensors.

        Args:
            sensor_name: The name of the sensor to query. Defaults to None for a global range.

        Returns:
            A tuple of (min, max) timestamps, or None if the sensor is not found, or no sensors
            are registered.
        """
        if sensor_name is not None:
            # Get time range for a specific sensor
            sensor = self._sensors.get(sensor_name)
            if sensor and sensor.min_timestamp is not None and sensor.max_timestamp is not None:
                return (sensor.min_timestamp, sensor.max_timestamp)
            return None
        else:
            # Get global time range across all sensors
            if not self._sensors:
                return None

            all_min_ts = [s.min_timestamp for s in self._sensors.values() if s.min_timestamp is not None]
            all_max_ts = [s.max_timestamp for s in self._sensors.values() if s.max_timestamp is not None]

            if not all_min_ts or not all_max_ts:
                return None

            return (min(all_min_ts), max(all_max_ts))

    def get_all_sensors_at(self, timestamp_ms: float) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Retrieves a state snapshot of all registered sensors at a specific timestamp.

        Args:
            timestamp_ms: The simulation time (in ms) for the snapshot.

        Returns:
            A dictionary where keys are sensor names and values are the corresponding
            sensor data (including query metadata) at that time.
        """
        state_snapshot = {}
        for name, sensor_stream in self._sensors.items():
            state_snapshot[name] = sensor_stream.get_value_at(timestamp_ms)
        
        return state_snapshot

    @property
    def sensors(self) -> Dict[str, SensorStream]:
        """Returns the dictionary of registered sensor streams."""
        return self._sensors
