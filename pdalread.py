import csv

def create_2d_array_from_csv(csv_file, column_index):
  """Creates a 2D array from a CSV file, starting a new row when the value in the specified column changes.

  Args:
    csv_file: The path to the CSV file.
    column_index: The index of the column to check for changes (0-based indexing).

  Returns:
    A 2D array representing the data from the CSV file, grouped by changes in the specified column.
  """

  with open(csv_file, 'r') as file:
    reader = csv.reader(file)
    # Skip the header row if present
    next(reader, None)

    # Initialize the 2D array and the previous value
    array_2d = []
    current_row = []
    previous_value = 0

    csvoutput = open('component_csv/data_0.csv', 'w', newline='')
    writer = csv.writer(csvoutput)
    writer.writerow(['X','Y','Z','Intensity','ReturnNumber','NumberOfReturns','ScanDirectionFlag','EdgeOfFlightLine','Classification',
                     'ScanAngleRank','UserData','PointSourceId','GpsTime','Red','Green','Blue','ClusterID'])

    for row in reader:
      # Get the value from the specified column
      current_value = row[column_index]

      # If the value is different from the previous value, start a new row
      if current_value != previous_value:
        csvoutput.close()
        csvoutput = open('component_csv/data_' + str(int(float(current_value))) + '.csv', 'w', newline='')
        writer = csv.writer(csvoutput)
        writer.writerow(['X','Y','Z','Intensity','ReturnNumber','NumberOfReturns','ScanDirectionFlag','EdgeOfFlightLine','Classification',
                        'ScanAngleRank','UserData','PointSourceId','GpsTime','Red','Green','Blue','ClusterID'])
        if current_row:
          array_2d.append(current_row)
        current_row = [row]
        previous_value = current_value
      else:
        # Otherwise, add the row to the current row
        current_row.append(row)
        writer.writerow(row)

    # Add the last row to the array
    if current_row:
      array_2d.append(current_row)
    csvoutput.close()

  return array_2d

# Example usage:
csv_file = "output.csv"
column_index = 20

array_2d = create_2d_array_from_csv(csv_file, column_index)



# Print the 2D array
for row in array_2d:
  print(len(row))
