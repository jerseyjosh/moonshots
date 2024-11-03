import pandas as pd

def xy_group(
        x: pd.Series, 
        y: pd.Series, 
        n: int,
    ) -> tuple[pd.Series, pd.Series]:
    """
    Group x and y series into n groups.
    """
    groups = pd.qcut(x, n, labels=False, duplicates='drop')
    x_grouped = x.groupby(groups).mean()
    y_grouped = y.groupby(groups).mean()
    return x_grouped, y_grouped