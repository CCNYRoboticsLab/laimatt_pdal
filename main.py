#!~/anaconda3/bin/python
import subprocess
from datetime import datetime

# Define flags for processing
concrete_mask = False
process_crack = True
process_stain = False
process_spall = False  # if crack is not processed, spall won't be processed.
concrete_post_filter = False


def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp}: {message}")


def call_in_conda_env(script_command, conda_env_name="visualinspection113"):
    """
    Executes a given script command within a specified Conda environment.

    Parameters:
    - script_command: The command to run within the Conda environment.
    - conda_env_name: Optional. The name of the Conda environment to activate. Defaults to "visualinspection113".
    """
    # Construct the command to run the script within the Conda environment
    command = f"/bin/bash -c 'source /home/roboticslab/anaconda3/bin/activate {conda_env_name} && {script_command}'"
    # Execute the command
    subprocess.call(command, shell=True)


def main():  # sourcery skip: extract-duplicate-method
    # Replace your existing subprocess.call lines with call_in_conda_env function calls

    # Create output folder, run_timestamp subfolder
    log_message("Create output folder, run_timestamp subfolder.")
    call_in_conda_env("python /home/roboticslab/Developer/image2overlays/CreateRunTimestampDirectory.py")

    # UpdateRawMaskOverlayConfigs.py
    log_message("Create raw, mask, overlay, mvs folders in run_timestamp folder.")
    call_in_conda_env("python /home/roboticslab/Developer/image2overlays/UpdateRawMaskOverlayConfigs.py")

    if concrete_mask:
        log_message("Running concrete mask...")
        call_in_conda_env("python /home/roboticslab/Developer/image2overlays/concretemask.py")

    #     log_message("Running filter raw...")
    #     call_in_conda_env("python filterRaw.py")

    # Run crack related processing

    if process_crack:
        # Run crack related processing
        log_message("Running crack segmentation...")
        call_in_conda_env("python /home/roboticslab/Developer/image2overlays/cracksegmentation.py")

        # log_message("Running concrete mask...")
        # call_in_conda_env("python concretemask.py")
        if concrete_post_filter:
            log_message("Running concrete post filter...")
            call_in_conda_env("python /home/roboticslab/Developer/image2overlays/concretePostFilter.py")

        # log_message("Converting crack masks to 3 categories according to directions...")
        # call_in_conda_env("python crack23directions.py")

        log_message("Running crack overlay...")
        call_in_conda_env("python /home/roboticslab/Developer/image2overlays/crackoverlay_transparent.py")

        # log_message("Copying geolocation info to crack overlay...")
        # call_in_conda_env("python copy_geolocation_crack.py")

        # log_message("Convert overlay images to pointcloud. ")
        # call_in_conda_env("python overlay2pointcloud.py --damage_type crack")

        if process_spall:
            log_message("Creating spall overlay...")
            call_in_conda_env("python3 /home/roboticslab/Developer/image2overlays/crackmask2spalloverlay_transparent.py")

        #     log_message("Copying geolocation info to spall overlay...")
        #     call_in_conda_env("python3 copy_geolocation_spall.py")

        #     log_message("las2potree for spall overlay")
        #     call_in_conda_env("python3 overlay2pointcloud.py --damage_type spall")

        #     log_message("Convert to Potree. ")
        #     call_in_conda_env("python3 las2potree.py --damage_type spall")

    if process_stain:
        # Run stain related processing
        log_message("Running stain segmentation...")
        call_in_conda_env("python /home/roboticslab/Developer/image2overlays/stainsegmentation.py")

        if concrete_post_filter:
            log_message("Running concrete post filter...")
            call_in_conda_env("python /home/roboticslab/Developer/image2overlays/concretePostFilterStain.py")

        log_message("Running stain overlay...")
        call_in_conda_env("python /home/roboticslab/Developer/image2overlays/stainoverlay_transparent.py")
        exit()

        log_message("Copying geolocation info to stain overlay...")
        call_in_conda_env("python3 /home/roboticslab/Developer/image2overlays/copy_geolocation_stain.py")

        log_message("Convert overlay images to pointcloud. ")
        call_in_conda_env("python3 /home/roboticslab/Developer/image2overlays/overlay2pointcloud.py --damage_type stain")

        log_message("Convert to Potree. ")
        call_in_conda_env("python3 /home/roboticslab/Developer/image2overlays/las2potree.py --damage_type stain")

    log_message("Script sequence completed.")


if __name__ == "__main__":
    main()
