import csv
import pandas as pd

def sort_csv_by_column(csv_file, column_name):
  """Sorts a CSV file numerically by a specified column and replaces the original file.

  Args:
    csv_file: The path to the CSV file.
    column_name: The name of the column to sort by.

  Returns:
    None. The original CSV file is replaced with the sorted version.
  """

  # Read the CSV file into a Pandas DataFrame
  df = pd.read_csv(csv_file)

  # Sort the DataFrame by the specified column
  df_sorted = df.sort_values(by=column_name, ascending=True)

  # Save the sorted DataFrame back to the original CSV file
  df_sorted.to_csv(csv_file, index=False)

# Example usage:
csv_file = "test.csv"
column_name = "ClusterID"

sort_csv_by_column(csv_file, column_name)

