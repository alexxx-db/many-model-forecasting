# Databricks notebook source
# MAGIC %md
# MAGIC # Many Models Forecasting SA (MMFSA) Demo
# MAGIC This demo highlights how to configure MMF SA to use M4 competition data

# COMMAND ----------

# MAGIC %pip install -r ../requirements.txt --quiet
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Data preparation steps
# MAGIC We are using `datasetsforecast` package to download M4 data.
# MAGIC
# MAGIC M4 dataset contains a set of time series which we use for testing of MMF SA.
# MAGIC
# MAGIC Below we have developed a number of functions to convert M4 time series to the expected format.

# COMMAND ----------

import pathlib
import pandas as pd
import logging
logger = spark._jvm.org.apache.log4j
logging.getLogger("py4j.java_gateway").setLevel(logging.ERROR)
logging.getLogger("py4j.clientserver").setLevel(logging.ERROR)
from datasetsforecast.m4 import M4

# COMMAND ----------

# Make sure that the catalog and the schema exist
catalog = "solacc_uc"  # Name of the catalog we use to manage our assets
db = "mmf"  # Name of the schema we use to manage our assets (e.g. datasets)

_ = spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
_ = spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{db}")

# COMMAND ----------

# Number of time series
n = 100


def create_m4_daily():
    y_df, _, _ = M4.load(directory=str(pathlib.Path.home()), group="Daily")
    _ids = [f"D{i}" for i in range(1, n+1)]
    y_df = (
        y_df.groupby("unique_id")
        .filter(lambda x: x.unique_id.iloc[0] in _ids)
        .groupby("unique_id")
        .apply(transform_group)
        .reset_index(drop=True)
    )
    return y_df


def transform_group(df):
    unique_id = df.unique_id.iloc[0]
    _start = pd.Timestamp("2020-01-01")
    _end = _start + pd.DateOffset(days=int(df.count()[0]) - 1)
    date_idx = pd.date_range(start=_start, end=_end, freq="D", name="ds")
    res_df = pd.DataFrame(data=[], index=date_idx).reset_index()
    res_df["unique_id"] = unique_id
    res_df["y"] = df.y.values
    return res_df


(
    spark.createDataFrame(create_m4_daily())
    .write.format("delta").mode("overwrite")
    .saveAsTable(f"{catalog}.{db}.m4_daily_train")
)

# COMMAND ----------

# MAGIC %md ### Now the dataset looks in the following way:

# COMMAND ----------

# MAGIC %sql select * from solacc_uc.mmf.m4_daily_train where unique_id in ('D1', 'D2', 'D6', 'D7', 'D10') order by unique_id, ds

# COMMAND ----------

# MAGIC %md ### Let's configure the list of models we are going to use for training:

# COMMAND ----------

active_models = [
    "ChronosT5Large",
]

# COMMAND ----------

# MAGIC %md ### Now we can run the forecasting process using `run_forecast` function.

# COMMAND ----------

# MAGIC %md
# MAGIC We have to loop through the model in the following way else cuda will throw an error.

# COMMAND ----------

for model in active_models:
  dbutils.notebook.run(
    "run_foundation_daily",
    timeout_seconds=0, 
    arguments={"catalog": catalog, "db": db, "model": model})

# COMMAND ----------

# MAGIC %md ### Evaluation output
# MAGIC In the evaluation output table, the evaluation for all backtest windows and all models are stored. This info can be used to monitor model performance or decide which models should be taken into the final aggregated forecast.

# COMMAND ----------

# MAGIC %sql select * from solacc_uc.mmf.daily_evaluation_output order by unique_id, model, backtest_window_start_date

# COMMAND ----------

# MAGIC %md ### Forecast Output
# MAGIC In the Forecast output table, the final forecast for each model and each time series is stored. 

# COMMAND ----------

# MAGIC %sql select * from solacc_uc.mmf.daily_scoring_output order by unique_id, model, ds

# COMMAND ----------

# MAGIC %md ### Ensemble Output
# MAGIC In the final ensemble output table, we store the averaged forecast. The models which meet the threshold defined using the ensembling parameters are taken into consideration

# COMMAND ----------

# MAGIC %sql select * from solacc_uc.mmf.daily_ensemble_output order by unique_id, model, ds

# COMMAND ----------

# MAGIC %md ### Delete Tables

# COMMAND ----------

# MAGIC #%sql delete from solacc_uc.mmf.daily_evaluation_output

# COMMAND ----------

# MAGIC #%sql delete from solacc_uc.mmf.daily_scoring_output

# COMMAND ----------

# MAGIC #%sql delete from solacc_uc.mmf.daily_ensemble_output
