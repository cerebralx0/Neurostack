"""
LSL-like object to stream data to multiple channels. Some code and helper
methods taken from https://github.com/kaczmarj/rteeg
"""
import numpy as np
import pylsl
import threading
import copy


def look_for_eeg_stream():
    """returns an inlet of the first eeg stream outlet found."""
    print("looking for an EEG stream...")
    streams = pylsl.resolve_byprop('type', 'EEG', timeout=30)
    if len(streams) == 0:
        raise (RuntimeError, "Can't find EEG stream")
    print("Start acquiring data")
    eeg_inlet = pylsl.StreamInlet(streams[0], max_chunklen=1)

    return eeg_inlet


class DataStream:

    def __init__(self):
        """Initializes data stream"""
        self.channels = {}

        self._eeg_thread = None
        self._eeg_thread_active = False
        self._eeg_inlet = None
        self._eeg_channel_names = None

    #
    # Connection methods
    #

    def lsl_connect(self):
        """Connects to LSL stream"""
        # get stream
        self._eeg_inlet = look_for_eeg_stream()
        info = self._eeg_inlet.info()

        # get channel names
        ch_names = []
        this_child = info.desc().child('channels').child('channel')
        for _ in range(info.channel_count()):
            ch_names.append(this_child.child_value('label'))
            this_child = this_child.next_sibling('channel')
        self._eeg_channel_names = ch_names

    def lsl_start(self):
        """Start recording data from LSL stream"""
        self._eeg_thread_active = True

        # record data to channels
        self._eeg_thread = threading.Thread(target=self._record_lsl_data_indefinitely,
                                            name='lsl')
        self._eeg_thread.daemon = True
        self._eeg_thread.start()

    def lsl_stop(self):
        """Stop recording data from LSL stream"""
        self._eeg_thread_active = False
        self._eeg_thread = None

    def _record_lsl_data_indefinitely(self):
        """
        Record LSL data indefinitely

        :param channel_names: channel names to stream samples to
        :return: does not return
        """
        # create channels
        for channel_name in self._eeg_channel_names:
            if channel_name not in self.list_channels():
                self.add_channel(channel_name)

        # continuously pull data
        while self._eeg_thread_active:
            samples, timestamp = self._eeg_inlet.pull_sample()
            time_correction = self._eeg_inlet.time_correction()

            # add pulled samples to channels
            for i in range(len(samples)):
                self.add_data(self._eeg_channel_names[i],
                              [timestamp + time_correction] + [samples[i]])

    def add_channel(self, name):
        """
        Adds a channel to the data stream

        :param name: name of channel to add
        :return: None
        """
        if self.channels.get(name) is not None:
            print("Channel with name {0} already exists".format(name))
        else:
            self.channels[name] = []

    def remove_channel(self, name):
        """
        Removes a channel from the data stream

        :param name: name of channel to remove
        :return: None
        """
        if self.channels.get(name) is None:
            print("Channel with name {0} does not exist".format(name))
        else:
            self.channels.pop(name)

    def close(self):
        """Close all connections"""
        self.channels = {}

    #
    # Methods for processing data
    #

    def get_data(self, channels, start_time=None, duration=None):
        """
        Takes a (copy of a) slice of data from channels at start_time for
        duration

        TODO: figure out if we should return the timestamp with the data or
        just the data

        :param channels: channel or list of channels to query
        :param start_time: start time for data. If None, returns all data
        :param duration: duration of data to get. If None, returns all data
                         after start time
        :return: a list of data if there is only 1 channel given, else a dict
                 with channel names as keys and data as values.
        """
        # get data for 1 channel--just return a list
        # TODO: do with binary search
        if not isinstance(channels, list):
            channel = channels

            # check to see that channel exists
            if self.channels.get(channel) is None:
                raise Exception(f"A channel with name {channel} does not exist")

            # return all the data for channel if start time is not specified
            if start_time is None:
                return self.channels[channel][:]

            # find start index
            start = 0
            while start_time > self.channels[channel][start][0]:
                start += 1
                if start == len(self.channels[channel]):
                    return []

            # return all the data starting from start time if duration is not
            # specified
            if duration is None:
                return self.channels[channel][start:]

            # find stop index
            stop_time = start_time + duration
            end = start
            while end < len(self.channels[channel]) and \
                stop_time > self.channels[channel][end][0]:
                end += 1

            # return time slice from start time to start time + duration if
            # both are specified
            return self.channels[channel][start:end]

        # get data for multiple channels--return a dict
        return_data = {}

        for channel in channels:
            return_data[channel] = self.get_data(channel, start_time, duration)

        return return_data

    def get_eeg_data(self, start_time=None, duration=None):
        """
        Get data from EEG channels

        :param start_time: start time for data. If None, returns all data
        :param duration: duration of data to get. If None, returns all data
                         after start time
        :return:
        """
        return self.get_data(channels=self._eeg_channel_names,
                             start_time=start_time,
                             duration=duration)

    def get_latest_data(self, channels):
        """
        Gets (a copy of the) latest data entry from channels

        :param channels:
        :return: a list of data if there is only 1 channel given, else a dict
        with channel names as keys and data as values.
        """
        if not isinstance(channels, list):
            return self.channels[channels][-1]

        return_data = {}

        for channel in channels:
            if self.channels.get(channel) is not None:
                # If the channel has no data (is empty)
                if not self.channels[channel]:
                    return_data[channel] = []
                else:
                    return_data[channel] = self.get_latest_data(channel)

            else:
                print(f"A channel with name {channel} does not exist")

        return return_data

    def add_data(self, channel, data):
        """
        TODO: decide on / find out about the specific requirements of the data
        Add data to channel

        :param channel:
        :param data:
        :return:
        """
        if self.channels.get(channel) is not None:
            self.channels[channel].append(data)
        else:
            print(f"A channel with name {channel} does not exist")

    def remove_data(self, channel, data):
        """
        TODO: decide on / find out about the specific requirements of the data
        Remove a specific piece of data from a channel

        :param channel:
        :param data:
        :return:
        """
        if self.channels.get(channel) is not None:
            try:
                self.channels[channel].remove(data)
            except ValueError:
                raise (ValueError, f"{data} data does not exist in the channel named {channel}")
        else:
            print(f"A channel with name {channel} does not exist")

    def has_data(self, channel):
        """
        Checks if a specific channel has any data.

        :param channel: channel
        :return: True if the channel has data, False otherwise
        """
        return not len(self.channels.get(channel, [])) == 0

    #
    # Stream information
    #

    def list_channels(self):
        """Returns a list of all the channels"""
        return list(self.channels.keys())
