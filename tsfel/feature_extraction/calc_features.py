import pandas as pd
import numpy as np
import glob
import json
import toml
import numbers
from tsfel.utils.signal_processing import merge_time_series, signal_window_spliter


def dataset_features_extractor(dictionary, dataset_configurator, pre_process=None):

    dcfg = toml.load(dataset_configurator)
    sensor_data = {}
    for sensor, ax in dcfg['ontology'].items():
        data = pd.read_csv(dcfg['dataset']['main_path'] + sensor + ".txt", header = None)
        sensor_data[sensor] = data.iloc[:, ax]

    pp_sensor_data = sensor_data if pre_process is None else pre_process(sensor_data)

    return pp_sensor_data


def pre_process(sensor_data):
    sensor_data['Accelerometer'].iloc[:, 1] = sensor_data['Accelerometer'].iloc[:, 1] - 10

    return sensor_data


def dataset_features_extractor2(dictionary, directory, window_size, overlap=0, fs_resample=30, time_unit=1e9, files_selection=None):

    output_settings = {'fs_resample': fs_resample, 'window_size': window_size, 'overlap': overlap,
                       'time_unit': time_unit, 'files_index': []}

    if files_selection is None:
        all_files = np.concatenate((glob.glob(directory+'/*.txt'), glob.glob(directory+'/*.csv')))
        data = [pd.read_csv(fl, header=None) for fl in all_files]
        output_settings['files_index'] = [[i, sensor_name.split('/')[-1]] for i, sensor_name in enumerate(all_files)]
    else:
        data = [pd.read_csv(directory + '/' + fl_s, header=None) for fl_s in files_selection]
        output_settings['files_index'] = [[i, sensor_name] for i, sensor_name in enumerate(files_selection)]

    data_new = merge_time_series(data, fs_resample, time_unit)

    windows = signal_window_spliter(data_new, window_size, overlap)

    features = time_series_features_extractor(dictionary, windows, fs=fs_resample)

    features.to_csv(directory + '/Features.csv', sep=',', encoding='utf-8')

    with open(directory + '/output_settings.json', 'w') as fp:
        json.dump(output_settings, fp)

    return features


def time_series_features_extractor(dictionary, signal_windows, fs=100):
    """

    :param dictionary: dictionary with selected features from json file
    :param signal_windows: list of signal windows
    :param ts_id: time series id to be concatenated with feature name
    :param fs: sampling frequency
    :return: features values for each window size
    """
    feat_val = pd.DataFrame()
    if isinstance(signal_windows[0], numbers.Real):
        signal_windows = [signal_windows]
    print("*** Feature extraction started ***")
    for wind_idx, wind_sig in enumerate(signal_windows):
        features = calc_window_features(dictionary, wind_sig, fs)
        feat_val = feat_val.append(features)
    print("*** Feature extraction finished ***")

    return feat_val


def calc_window_features(dictionary, signal_window, fs):
    """
    This function computes features matrix for one window.
    :param dictionary: (json file)
           list of features
    :param signal_window: (pandas DataFrame)
           input from which features are computed, window.
    :param fs: (int)
           sampling frequency
    :return: res: (narray-like)
             values of each features for signal.
             nam: (narray-like)
             names of the features
    """
    domain = dictionary.keys()

    # Create global arrays
    func_total = []
    func_names = []
    imports_total = []
    parameters_total = []
    free_total = []

    for atype in domain:
        domain_feats = dictionary[atype].keys()

        for feat in domain_feats:
            # Only returns used functions
            if dictionary[atype][feat]['use'] == 'yes':

                # Read Function Name (generic name)
                func_names += [feat]

                # Read Function (real name of function)
                func_total += [dictionary[atype][feat]['function']]

                # Read Parameters
                parameters_total += [dictionary[atype][feat]['parameters']]

                # Read Free Parameters
                free_total += [dictionary[atype][feat]['free parameters']]

    # Execute imports
    exec("import tsfel")

    # Name of each column to be concatenate with feature name
    if not isinstance(signal_window, pd.DataFrame):
        signal_window = pd.DataFrame(data=signal_window)
    header_names = signal_window.columns.values

    feature_results = []
    feature_names = []

    for ax in range(len(header_names)):
        window = signal_window.iloc[:, ax]
        for i in range(len(func_total)):

            execf = func_total[i] + '(window'

            if parameters_total[i] != '':
                execf += ', ' + parameters_total[i]

            if free_total[i] != '':
                for n, v in free_total[i].items():
                    # TODO: conversion may loose precision (str)
                    execf += ', ' + n + '=' + str(v)

            execf += ')'

            eval_result = eval(execf, locals())

            # Function returns more than one element
            if type(eval_result) == tuple:
                for rr in range(len(eval_result)):
                    if np.isnan(eval_result[0]):
                        eval_result = np.zeros(len(eval_result))
                    feature_results += [eval_result[rr]]
                    feature_names += [str(header_names[ax]) + '_' + func_names[i] + '_' + str(rr)]
            else:
                feature_results += [eval_result]
                feature_names += [str(header_names[ax]) + '_' + func_names[i]]

    feature_results = np.array(feature_results)
    features = pd.DataFrame(data=feature_results.reshape(1, len(feature_results)), columns=feature_names)
    return features
