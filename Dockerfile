# Use an official Python runtime as a parent image
FROM pdal/pdal

# # Set environment variables
# ENV PATH /opt/conda/bin:$PATH

# # Update Conda and install basic dependencies
# RUN conda update -n base -c defaults conda && \
#     apt-get update && apt-get install -y \
#     build-essential \
#     wget \
#     && apt-get clean

# # Create and activate a Python 3.8 environment
# RUN conda create --name myenv python=3.11.9
# RUN echo "source activate myenv" > ~/.bashrc
# ENV PATH /opt/conda/envs/myenv/bin:$PATH

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies
RUN apt-get update 
    # && conda activate app/pdal 
    # && pip install pandas laspy mysql-connector-python requests flask pdal    

RUN echo "source activate pdal" > ~/.bashrc
ENV PATH /opt/conda/envs/pdal:$PATH

RUN conda install pandas laspy mysql-connector-python requests flask  

EXPOSE 33333

ENV NAME laimatt

# Run your application
# CMD ["conda", "run", "-n", "pdal", "python", "fullcall_ODM_API.py"]
CMD ["conda", "run", "-n", "pdal", "python", "-m" , "flask", "--app", "fullcall_ODM_API", "run", "--host=0.0.0.0"]
