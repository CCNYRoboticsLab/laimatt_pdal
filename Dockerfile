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
RUN apt-get update &&\ 
    apt-get install -y python3 python3-dev python3-pip &&\
    pip3 install -r requirements.txt

# Set tini as the entry point
ENTRYPOINT ["/usr/bin/tini", "--"]

EXPOSE 33333

ENV NAME=laimatt

# Run your application
CMD ["bash", "run.sh"]
