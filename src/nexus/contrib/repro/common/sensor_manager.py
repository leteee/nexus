# src/nexus/contrib/repro/common/sensor_manager.py

import json
import logging
import heapq
from bisect import bisect_left
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

class SensorStream:
    """
    Manages and provides time-based access to a single stream of sensor data from a JSONL file.
    It supports data delays and provides efficient time-based queries using multiple strategies.
    """

    def __init__(self, data_path: str, time_offset_ms: float = 0, tolerance_ms: float = float('inf')):
        """
        Initializes the stream by loading, parsing, and sorting data from the given file.
        """
        self.data_path = data_path
        self.time_offset_ms = time_offset_ms
        self.tolerance_ms = tolerance_ms
        
        # Each stream gets its own logger, named after the data file for easy debugging.
        self.logger = logging.getLogger(f"{__name__}.SensorStream.{Path(data_path).stem}")

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
        self.logger.info(f"Loading data from: {self.data_path}")
        temp_data = []
        try:
            with open(self.data_path, "r", encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        if "timestamp_ms" not in record:
                            error_msg = f"Record in {self.data_path} is missing 'timestamp_ms': {record}"
                            self.logger.error(error_msg)
                            raise ValueError(error_msg)
                        temp_data.append(record)
        except FileNotFoundError:
            self.logger.error(f"Data file not found at: {self.data_path}")
            raise
        
        temp_data.sort(key=lambda x: x["timestamp_ms"])
        
        self._data = temp_data
        self._timestamps = [d["timestamp_ms"] for d in self._data]
        self.logger.info(f"Loaded and sorted {len(self._data)} records from {self.data_path}.")

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
            self.logger.warning("No data loaded, cannot get value.")
            return None

        # 1. Get the strategy implementation from the dispatch table
        strategy_fn = self._match_strategies.get(strategy)
        if not strategy_fn:
            error_msg = f"Strategy '{strategy}' is not implemented. Available strategies are: {list(self._match_strategies.keys())}"
            self.logger.error(error_msg)
            raise NotImplementedError(error_msg)

        # 2. Calculate the aligned time for lookup
        aligned_time_ms = snapshot_time_ms - self.time_offset_ms

        # 3. Find the index of the best match using the chosen strategy
        self.logger.debug(f"Searching for data at aligned_time_ms={aligned_time_ms} with strategy='{strategy}'")
        matched_index = strategy_fn(aligned_time_ms)

        if matched_index is None:
            self.logger.debug(f"No data found for aligned_time_ms={aligned_time_ms} with strategy='{strategy}'")
            return None

        # 4. Check if the found data is within the tolerance
        matched_time_ms = self._timestamps[matched_index]
        if abs(matched_time_ms - aligned_time_ms) > self.tolerance_ms:
            self.logger.debug(
                f"Data at {matched_time_ms} is outside tolerance ({self.tolerance_ms}ms) "
                f"for aligned_time_ms={aligned_time_ms}"
            )
            return None

        # 5. Get the matched data and augment it with traceability info
        matched_data = self._data[matched_index]
        result = matched_data.copy()
        result['snapshot_time_ms'] = snapshot_time_ms
        result['aligned_time_ms'] = aligned_time_ms
        self.logger.debug(f"Found match at index {matched_index}: {result}")
        return result

    def __len__(self):
        return len(self._data)


class _SensorEventIterator:
    """
    A stateful iterator that merges multiple sensor streams and yields events
    in chronological order, ensuring each data point is processed exactly once.
    """

    def __init__(self, sensors: Dict[str, SensorStream]):
        self._sensors = sensors
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._heap: List[Tuple[float, str, int]] = []

        # Initialize the heap with the first event from each non-empty sensor stream
        for name, stream in self._sensors.items():
            if stream and len(stream) > 0:
                # Adjust for the sensor's individual time offset to get "world time"
                timestamp = stream._timestamps[0] + stream.time_offset_ms
                heapq.heappush(self._heap, (timestamp, name, 0))
                self.logger.debug(f"Pushed initial event for '{name}' at timestamp {timestamp}")

    def __iter__(self):
        return self

    def __next__(self) -> Dict[str, Any]:
        """
        Yields the next chronological event snapshot from the merged sensor streams.
        Groups events that occur at the exact same timestamp.
        """
        if not self._heap:
            self._logger.info("Event iteration finished.")
            raise StopIteration

        # Pop the next chronological event
        current_ts, sensor_name, data_index = heapq.heappop(self._heap)
        
        # This snapshot will contain all sensor data for the current timestamp
        snapshot = {
            'timestamp': current_ts,
            'sensors': {
                sensor_name: self._sensors[sensor_name]._data[data_index]
            }
        }
        self._logger.debug(f"Popped event for '{sensor_name}' at {current_ts}")

        # Advance the cursor for the stream we just popped from
        self._push_next_for(sensor_name, data_index + 1)

        # --- Group simultaneous events ---
        # Keep popping from the heap as long as the next event has the same timestamp
        while self._heap and self._heap[0][0] == current_ts:
            _, same_ts_sensor_name, same_ts_data_index = heapq.heappop(self._heap)
            
            self._logger.debug(f"Popped simultaneous event for '{same_ts_sensor_name}' at {current_ts}")
            snapshot['sensors'][same_ts_sensor_name] = self._sensors[same_ts_sensor_name]._data[same_ts_data_index]
            
            # Advance the cursor for this stream as well
            self._push_next_for(same_ts_sensor_name, same_ts_data_index + 1)

        return snapshot

    def _push_next_for(self, sensor_name: str, next_index: int):
        """
        Pushes the next event from a given sensor stream onto the heap if available.
        """
        stream = self._sensors[sensor_name]
        if next_index < len(stream):
            # Calculate the "world time" of the next event, including the sensor's offset
            timestamp = stream._timestamps[next_index] + stream.time_offset_ms
            heapq.heappush(self._heap, (timestamp, sensor_name, next_index))
            self._logger.debug(f"Pushed next event for '{sensor_name}' at {timestamp} (index {next_index})")
        else:
            self._logger.debug(f"Sensor stream '{sensor_name}' exhausted.")


class SensorDataManager:
    """
    A central manager for multiple SensorStream objects.
    
    It allows registering sensors with individual time offsets and provides time-range queries
    and synchronized state snapshots at any given point in time.
    """

    def __init__(self):
        """
        Initializes the SensorDataManager.
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        self._sensors: Dict[str, SensorStream] = {}
        self.logger.info("SensorDataManager initialized.")


    def register_sensor(self, name: str, data_path: str, time_offset_ms: float = 0, tolerance_ms: float = float('inf')):
        """
        Registers a new sensor stream with the manager.

        Args:
            name: A unique name for the sensor (e.g., 'gps', 'imu_1').
            data_path: The path to the sensor's JSONL data file.
            time_offset_ms: The inherent time offset of this sensor in milliseconds.
            tolerance_ms: The time window in ms for which a match is considered valid.
        """
        if name in self._sensors:
            error_msg = f"Sensor with name '{name}' is already registered."
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.logger.info(f"Registering sensor '{name}' with data from '{data_path}', offset {time_offset_ms}ms, tolerance {tolerance_ms}ms.")
        self._sensors[name] = SensorStream(
            data_path,
            time_offset_ms=time_offset_ms,
            tolerance_ms=tolerance_ms,
        )

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
        self.logger.debug(f"Querying time range for sensor: '{sensor_name or 'all'}'")
        if sensor_name is not None:
            # Get time range for a specific sensor
            sensor = self._sensors.get(sensor_name)
            if sensor and sensor.min_timestamp is not None and sensor.max_timestamp is not None:
                return (sensor.min_timestamp, sensor.max_timestamp)
            self.logger.warning(f"Could not determine time range for sensor '{sensor_name}'. It may not exist or be empty.")
            return None
        else:
            # Get global time range across all sensors
            if not self._sensors:
                self.logger.warning("No sensors registered, cannot determine global time range.")
                return None

            all_min_ts = [s.min_timestamp for s in self._sensors.values() if s.min_timestamp is not None]
            all_max_ts = [s.max_timestamp for s in self._sensors.values() if s.max_timestamp is not None]

            if not all_min_ts or not all_max_ts:
                self.logger.warning("Could not determine global time range. Some sensors may be empty.")
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
        self.logger.debug(f"Getting all sensor values at timestamp_ms: {timestamp_ms}")
        state_snapshot = {}
        for name, sensor_stream in self._sensors.items():
            state_snapshot[name] = sensor_stream.get_value_at(timestamp_ms)
        
        return state_snapshot

    def iter_events(self) -> "_SensorEventIterator":
        """
        Returns a stateful iterator that yields chronologically sorted event snapshots.

        Each snapshot contains all sensor data that occurred at a specific timestamp.
        This method is ideal for processing each sensor measurement exactly once.

        Each call to this method returns a new, independent iterator.

        Yields:
            Dict[str, Any]: A snapshot dictionary containing the 'timestamp' and
                            a 'sensors' dictionary with the data for that timestamp.
        
        Example:
            >>> for snapshot in manager.iter_events():
            ...     print(f"Time: {snapshot['timestamp']}, Data: {snapshot['sensors']}")
        """
        self.logger.info("Creating a new sensor event iterator.")
        return _SensorEventIterator(self._sensors)

    @property
    def sensors(self) -> Dict[str, SensorStream]:
        """Returns the dictionary of registered sensor streams."""
        return self._sensors


class SensorPlayback:
    """
    Provides a stateful mechanism to play back sensor data in chronological order
    based on an externally advancing clock.

    This class is designed to be controlled by an external simulation loop. It keeps
    track of which sensor events have been consumed and, on each call to `advance()`,
    returns a batch of all new events that have occurred in the latest time slice.
    """

    def __init__(self, data_manager: SensorDataManager):
        """
        Initializes the SensorPlayback object.

        Args:
            data_manager: A fully configured SensorDataManager instance.
        """
        self._manager = data_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize cursors for each stream to track consumption
        self._cursors: Dict[str, int] = {name: 0 for name in self._manager.sensors}
        
        # Start time is initialized to negative infinity to ensure the very first
        # call to advance() captures all events from the beginning up to the first timestamp.
        self._last_known_time_ms: float = float('-inf')
        
        self.logger.info("SensorPlayback initialized. Cursors set to 0 for all sensors.")

    def advance(self, current_time_ms: float) -> Dict[str, List[Dict[str, Any]]]:
        """
        Advances the playback time and returns all new sensor events since the last call.

        This method is stateful. It finds all events with a timestamp greater than
        the last known time and less than or equal to the new `current_time_ms`.

        Args:
            current_time_ms: The new "now" from the external clock.

        Returns:
            A dictionary where keys are sensor names and values are a list of
            new sensor data records that occurred in the time slice. An empty
            dictionary is returned if no new events occurred.
        """
        if current_time_ms < self._last_known_time_ms:
            self._logger.warning(
                f"Time is moving backwards. Ignoring advance call from "
                f"{self._last_known_time_ms} to {current_time_ms}."
            )
            return {}

        self._logger.debug(
            f"Advancing from {self._last_known_time_ms} to {current_time_ms}"
        )
        
        new_events_by_sensor: Dict[str, List[Dict[str, Any]]] = {}

        for name, stream in self._manager.sensors.items():
            start_index = self._cursors[name]
            events_in_slice: List[Dict[str, Any]] = []

            # Iterate through the stream's data from the last known position
            for i in range(start_index, len(stream)):
                record = stream._data[i]
                # The event's "world time" includes its own inherent offset
                event_ts = record["timestamp_ms"] + stream.time_offset_ms

                if self._last_known_time_ms < event_ts <= current_time_ms:
                    # This event is within our new time slice
                    events_in_slice.append(record)
                
                if event_ts > current_time_ms:
                    # We have passed our current time window. The next search should start here.
                    self._cursors[name] = i
                    break
            else:
                # If the loop completes without breaking, we've consumed the entire stream
                self._cursors[name] = len(stream)

            if events_in_slice:
                new_events_by_sensor[name] = events_in_slice
        
        # Update the clock for the next call
        self._last_known_time_ms = current_time_ms
        
        return new_events_by_sensor

