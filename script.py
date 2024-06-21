import laspy

def get_center_point(las_file_path):
    with laspy.open(las_file_path) as f:
        x_min, x_max = f.header.x_min, f.header.x_max
        y_min, y_max = f.header.y_min, f.header.y_max
        z_min, z_max = f.header.z_min, f.header.z_max

        center_x = (x_min + x_max) / 2
        center_y = (y_min + y_max) / 2
        center_z = (z_min + z_max) / 2

        return center_x, center_y, center_z

# Example usage
las_file_path = "3sections - 170 - 253.las"
center_point = get_center_point(las_file_path)
print(f"Center point: {center_point}")