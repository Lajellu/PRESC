from presc.evaluations.utils import get_bins, is_discrete
from presc.utils import include_exclude_list

from pandas import DataFrame, Series
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt

# Set here temporarily
METRIC = accuracy_score


def compute_conditional_metric(
    grouping_col,
    true_labs,
    pred_labs,
    metric,
    as_categorical=False,
    num_bins=10,
    quantile=False,
):
    """Compute metric values conditional on the grouping column.

    The metric is computed within unique values of the grouping column
    (categorical) or within bins partitioning its range (continuous).

    grouping_col: Series defining a grouping for the metric computation
    true_labs: Series of true labels for a test dataset
    pred_labs: Series of labels predicted by a model for a test dataset
    metric: the evaluation metric to compute across the groupings. This should be
        a function f(y_true, y_pred) which accepts Series of true and
        predicted labels.
    as_categorical: should the grouping column be treated as categorical, ie. binned
        on its unique values? If it is not numeric, this param is ignored.
    num_bins: number of bins to use for grouping a numeric column
    quantile: should the bin widths correpond to quantiles of a numerical column's
        distribution (`True`) or be equally-spaced over its range (`False`)

    Returns a `ConditionalMetricResult` instance.
    """

    y_vals = DataFrame({"y_true": true_labs, "y_pred": pred_labs})
    if is_discrete(grouping_col):
        as_categorical = True
    if as_categorical:
        grouping = grouping_col
        bins = grouping.unique()
    else:
        grouping, bins = get_bins(grouping_col, num_bins, quantile)
    binned_metric_vals = y_vals.groupby(grouping).apply(
        lambda gp: metric(gp["y_true"], gp["y_pred"])
    )

    return ConditionalMetricResult(
        vals=binned_metric_vals,
        bins=Series(bins),
        categorical=as_categorical,
        num_bins=num_bins,
        quantile=quantile,
    )


class ConditionalMetricResult:
    """Result of the conditional metric evaluation for a single grouping.

    vals: a Series listing the computation result for each bin
    bins: a Series listing the bin endpoints. If the feature was treated as
        numeric, this will have length `len(vals)+1`, otherwise `len(vals)`.
    categorical: was the feature treated as categorical?
    config: dict of config options
    num_bins: number of bins used for grouping
    quantile: was grouping quantile-based?
    """

    def __init__(self, vals, bins, categorical, num_bins, quantile):
        self.vals = vals
        self.bins = bins
        self.categorical = categorical
        self.num_bins = num_bins
        self.quantile = quantile

    def display_result(self, xlab, ylab):
        """Display the evaluation result for the given grouping and metric.

        xlab: label to display on the x-axis
        ylab: label to display on the y-axis

        """

        if self.categorical:
            result_edges = self.bins.astype("str")
            alignment = "center"
            # width_interval = 1
        else:
            result_edges = self.bins[:-1]
            alignment = "edge"
            # First element will be NaN.
            bin_widths = self.bins.diff()[1:]
            # width_interval = bin_widths * self.config["plot_width_fraction"]

        plt.ylim(0, 1)
        plt.xlabel(xlab)
        plt.ylabel(ylab)
        plt.bar(
            result_edges,
            self.vals,
            # width=width_interval,
            width=bin_widths,
            bottom=None,
            align=alignment,
            edgecolor="white",
            linewidth=2,
        )
        plt.show(block=False)


class ConditionalMetric:
    """Computation of confusion-based metrics across subsets of a test dataset.

    model: the ClassificationModel to run the evaluation for
    test_dataset: a Dataset to use for evaluation.
    config: the main config dict
    """

    def __init__(self, model, test_dataset, config):
        self._config = config["evaluations"]["conditional_metric"]
        self._model = model
        self._test_dataset = test_dataset
        self._test_pred = self._model.predict_labels(test_dataset)

    def compute_for_column(self, colname, metric, **kwargs):
        """Compute the evaluation for the given dataset column.

        The metric is computed within unique values of the specified column
        (if categorical) or within bins partitioning its range (if continuous).

        colname: a column in the dataset to partition on
        metric: the evaluation metric to compute across the partitions. This should be
            a function f(y_true, y_pred) which accepts Series of true and
            predicted labels.
        kwargs: overrides to the default option values for the computation.

        Returns a `ConditionalMetricResult` instance.
        """
        comp_config = dict(self._config["computation"])
        col_overrides = comp_config.pop("columns", {})
        if col_overrides:
            comp_config.update(col_overrides.get(colname, {}))
        comp_config.update(kwargs)

        return compute_conditional_metric(
            grouping_col=self._test_dataset.df[colname],
            true_labs=self._test_dataset.labels,
            pred_labs=self._test_pred,
            metric=metric,
            as_categorical=comp_config["as_categorical"],
            num_bins=comp_config["num_bins"],
            quantile=comp_config["quantile"],
        )

    def display(self, colnames=None, metric_name="Metric value"):
        """Computes and displays the conditional metric result for each specified column.

        colnames: a list of column names to run the evaluation over, creating a plot
            for each. If not supplied, defaults to columns specifed in the
            config.
        metric_name: display name identifying the metric to show on the plot
        """
        if colnames:
            incl = colnames
            excl = None
        else:
            incl = self._config["columns_include"]
            excl = self._config["columns_exclude"]
        cols = include_exclude_list(
            self._test_dataset.column_names, included=incl, excluded=excl
        )

        for colname in cols:
            # TODO: don't hardcode the metric
            eval_result = self.compute_for_column(colname, metric=METRIC)
            eval_result.display_result(xlab=colname, ylab=metric_name)
