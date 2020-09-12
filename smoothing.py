# -*- coding: utf-8 -*-
"""
Provides functions for smoothing and filtering of data rows oganized in 2D
numpy arrays.
"""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d
from sklearn.decomposition import PCA


def smoothing(raw_data, mode, interpolate=False, point_mirror=True, **kwargs):
    """
    Smoothes data rows with different algorithms.

    Parameters
    ----------
    raw_data : ndarray
        2D numpy array with the shape (N,M) containing N data rows to be
        smoothed. Each data row is represented by row in numpy array and
        contains M values. If only one data row is present, raw_data has the
        shape (1,M).
    mode : str
        Algorithm used for smoothing. Allowed modes are 'sav_gol' for Savitzky-
        Golay, 'rolling_median' for a median filter, 'pca' for smoothing based
        on principal component analysis, 'selective_moving_average' for a
        moving average that can decide if values in the window are used for
        averaging.
    interpolate : boolean
        False if x coordinate is evenly spaced. True if x coordinate is not
        evenly spaced, then raw_data is interpolated to an evenly spaced
        x coordinate. default=False
    point_mirror : boolean
        Dataset is point reflected at both end points before smoothing to
        reduce artifacts at the data edges.
    **kwargs for interpolate=True
        x_coordinate : ndarray
            1D numpy array with shape (M,) used for interpolation.
        data_points : int
            number of data points returned after interpolation. Default is one
            order of magnitude more than M.
    **kwargs for different smoothing modes
        sav_gol:
            deriv : int
                Derivative order to be calculated. Default is 0 (no
                derivative).
            savgol_points : int
                Number of point defining one side of the Savitzky-Golay window.
                Total window is 2*savgol_points+1. Default is 9.
            poly_order : int
                Polynomial order used for polynomial fitting of the Savitzky-
                Golay window. Default is 2.
            savgol_mode : str
                Must be ‘mirror’, ‘constant’, ‘nearest’, ‘wrap’ or ‘interp’.
                See documentation of scipy.signal.savgol_filter.
        rolling_median:
            window: int
                Data points included in rolling window used for median
                calculations. Default is 5.
        pca:
            pca_components : int
                Number of principal components used to reconstruct the original
                data. Default is 5.
        selective_moving_average:
            weights : list of bool
                The number of entries decide the window length used for
                smoothing. True means that the value is used, False means the
                value is excluded, e.g. [True, False, True] is a window of size
                3 in which the center point is exluded from the calculations.

    Returns
    -------
    ndarray or tuple of ndarrays
        2D numpy array containing the smoothed data in the same shape as
        raw_data if interpolate is false. Else tuple containing interpolated
        x coordinates and 2D numpy array in the shape of
        (N,10**np.ceil(np.log10(len(x_coordinate)))). In case of mode is
        selective_moving_average, the corresponding standard deviations are
        also calulated and a tuple with the smoothed data and the standard
        deviations is returned.

    """
    # copy of raw_data for later restoration of data edges
    raw_old = pd.DataFrame(raw_data.copy())
    # Preprocessing of input data for unevenly spaced x coordinate
    if interpolate:
        x_coordinate = kwargs.get('x_coordinate', np.linspace(
            0, 1000, raw_data.shape[1]))
        data_points = kwargs.get('data_points',
                                 int(10**np.ceil(np.log10(len(x_coordinate)))))

        itp = interp1d(x_coordinate, raw_data, kind='linear')
        x_interpolated = np.linspace(x_coordinate[0], x_coordinate[-1],
                                     data_points)
        raw_data = itp(x_interpolated)

    # Optional extension of smoothed data by point mirrored raw data.
    if point_mirror:
        raw_data = np.concatenate(
            ((-np.flip(raw_data, axis=1)+2*raw_data[:, 0, np.newaxis])[:, :-1],
             raw_data, (-np.flip(raw_data, axis=1) +
                        2*raw_data[:, -1, np.newaxis])[:, 1:]), axis=1)
        #raw_data = np.concatenate((-np.squeeze(raw_data.T)[::-1]+2*np.squeeze(raw_data.T)[0],np.squeeze(raw_data.T),-np.squeeze(raw_data.T)[::-1]+2*np.squeeze(raw_data.T)[-1]))[np.newaxis]
        print(raw_data)

    smoothing_modes = ['sav_gol', 'rolling_median', 'pca', 'selective_moving_average']

    if mode == smoothing_modes[0]:  # sav_gol
        deriv = kwargs.get('deriv', 0)
        savgol_points = kwargs.get('savgol_points', 9)
        poly_order = kwargs.get('poly_order', 2)
        savgol_mode = kwargs.get('savgol_mode', 'nearest')

        smoothed_data = savgol_filter(raw_data, 1+2*savgol_points, poly_order,
                                      deriv=deriv, axis=1, mode=savgol_mode)

    elif mode == smoothing_modes[1]:  # rolling_median
        window = kwargs.get('window', 5)
        # next line due to pandas rolling window, look for numpy solution
        raw_data = pd.DataFrame(raw_data)

        edge_value_count = int((window-1)/2)
        smoothed_data = raw_data.rolling(
                window, axis=1, center=True).median().iloc[
                :, edge_value_count:-edge_value_count]

        # On the data edges, the original data is used, so the edges are not
        # smoothed (only relevant if point_mirror is False).
        smoothed_data = pd.concat(
            [raw_old.iloc[:, 0:edge_value_count], smoothed_data,
             raw_old.iloc[:, -1-edge_value_count:]], axis=1).values

    elif mode == smoothing_modes[2]:  # pca
        pca_components = kwargs.get('pca_components', 5)

        pca = PCA(n_components=pca_components)
        scores = pca.fit_transform(raw_data)
        loadings = pca.components_

        smoothed_data = (
            np.dot(scores, loadings) + np.mean(raw_data, axis=0))

    elif mode == smoothing_modes[3]:  # selective_moving_average
        weights = kwargs.get('weights', [True, True, False, True, True])

        window_size = len(weights)
        value_count = raw_data.shape[1]
        edge_value_count = int((window_size-1)/2)
        remaining_values = value_count-window_size+1

        column_indices = np.repeat(
            np.arange(window_size)[np.newaxis], remaining_values, axis=0
            ) + np.arange(remaining_values)[:, np.newaxis]
        column_indices = column_indices[:, weights]

        value_array = np.squeeze(raw_data[np.newaxis][:, :, column_indices])
        if len(value_array.shape) == 2:
            value_array = value_array[np.newaxis]
        smoothed_data = pd.DataFrame(np.mean(value_array, axis=2))

        selective_std = np.std(value_array, axis=2)
        # On the edges, the std is calculated from the reduced number of edge
        # data points (only relevant if point_mirror is False).
        selective_std = np.concatenate((
            np.repeat(np.std(raw_old.values[:, 0:edge_value_count], axis=1),
                      edge_value_count).reshape(-1, edge_value_count),
            selective_std,
            np.repeat(np.std(raw_old.values[:, -edge_value_count:], axis=1),
                      edge_value_count).reshape(-1, edge_value_count)
            ), axis=1)

        # On the data edges, the original data is used, so the edges are not
        # smoothed (only relevant if point_mirror is False).
        raw_data = pd.DataFrame(raw_data)
        smoothed_data = pd.concat(
            [raw_old.iloc[:, 0:edge_value_count], smoothed_data,
             raw_old.iloc[:, -edge_value_count:]], axis=1).values

    else:
        raise ValueError('No valid smoothing mode entered. Allowed modes are '
                         '{0}'.format(smoothing_modes))

    # Removal of previously added point mirrored data.
    if point_mirror:
        smoothed_data = smoothed_data[
            :, int(np.ceil(smoothed_data.shape[1]/3)-1):
                int(2*np.ceil(smoothed_data.shape[1]/3)-1)]
        if mode == smoothing_modes[3]:  # selective_moving_average
            selective_std = selective_std[
                :, int(np.ceil(selective_std.shape[1]/3)-1):
                    int(2*np.ceil(selective_std.shape[1]/3)-1)]

    if interpolate:
        return (x_interpolated, smoothed_data)
    elif mode == smoothing_modes[3]:  # selective_moving_average
        return (smoothed_data, selective_std)
    else:
        return smoothed_data


def filtering(raw_data, mode, fill='NaN', **kwargs):
    """
    Filters data rows with different algorithms.

    Filtered values are replaced by np.nan.

    Parameters
    ----------
    raw_data : ndarray
        2D numpy array with the shape (N,M) containing N data rows to be
        filtered. Each data row is represented by row in numpy array and
        contains M values. If only one data row is present, raw_data has the
        shape (1,M).
    mode : str
        Algorithm used for filtering. Allowed modes are 'spike_filter' for
        sharp peaks, 'max_thresh' for removal of values above or equal to a
        maximum threshold, 'min_thresh' for removal of values below or equal to
        a minumum threshold.
    fill : str
        Decides the way filtered points are replaced. Currently only 'NaN'
        where values are placed by np.nan.
    **kwargs for different filter modes
        spike_filter:
            weights : list of bool
                The number of entries decide the window length used for
                rolling average and standard deviation calculation. True means
                that the value is used, False means the value is excluded, e.g.
                [True, False, True] is a window of size 3 in which the center
                point is exluded from the calculations. Default is [True, True,
                False, True, True]
            std_factor : float
                The number of standard deviations a value is allowed to be away
                from the moving average before it is removed by the filter.
                Mean and standard deviation are calculated in a rolling fashion
                so that only sharp peaks are found. Default is 2.
            point_mirror : bool
                Decides if the data edges are point mirrored before rolling
                average. If True, estimates of mean and standard deviation also
                at the edges are obtained. If False, data at the edges are kept
                like in the original. Default is False.
            interpolate : boolean
                False if x coordinate is evenly spaced. True if x coordinate is
                not evenly spaced, then raw_data is interpolated to an evenly
                spaced x coordinate. default=False
        max_thresh
            max:_thresh : float
                The maximum threshold. Default is 1000.
        min_thresh
            min_thresh : float
                The minimum threshold. Default is 0.

    Returns
    -------
    ndarray
        Returns an ndarray with dimensions like raw_data. Filtered points are
        changed according to the fill selected.

    """
    filter_modes = ['spike_filter', 'max_thresh', 'min_thresh']

    if mode == filter_modes[0]:  # spike_filter
        weights = kwargs.get('weights', [True, True, False, True, True])
        window_size = len(weights)
        std_factor = kwargs.get('std_factor', 2)
        point_mirror = kwargs.get('point_mirror', False)
        interpolate = kwargs.get('interpolate', False)

        mov_avg, mov_std = smoothing(
            raw_data, 'selective_moving_average', point_mirror=point_mirror,
            interpolate=interpolate, weights=weights)
        
        diffs = np.absolute(raw_data - mov_avg)
        raw_data[diffs > std_factor*mov_std] = np.nan
        filtered_data = raw_data
    elif mode == filter_modes[1]:  # max_thresh
        maximum_threshold = kwargs.get('max_thresh', 1000)
        raw_data = raw_data.astype(float)
        raw_data[raw_data > maximum_threshold] = np.nan
        filtered_data = raw_data
    elif mode == filter_modes[2]:  # min_thresh
        minimum_threshold = kwargs.get('min_thresh', 0)
        raw_data = raw_data.astype(float)
        raw_data[raw_data < minimum_threshold] = np.nan
        filtered_data = raw_data
    else:
        raise ValueError('No valid filter mode entered. Allowed modes are '
                         '{0}'.format(filter_modes))
        
    return filtered_data
