# Use an official Python runtime as a parent image
FROM pdal/pdal

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies
RUN apt-get update   

RUN apt-get install -y zsh libgl1-mesa-glx libglu1-mesa libglvnd0

RUN chmod +x run.sh

RUN conda env create -f environment_cors.yml

# Add retry mechanism and increase timeout for conda
# RUN conda config --set remote_read_timeout_secs 600 && \
#     for i in {1..3}; do \
#         conda env create -f environment_visinspect.yml && break || \
#         echo "Retry $i/3" && \
#         sleep 15; \
#     done

RUN conda config --set remote_read_timeout_secs 600 && conda env create -f environment_visinspect_2.yml 

RUN echo "source activate pdal_env" > ~/.bashrc
ENV PATH=/opt/conda/envs/pdal_env/bin:$PATH

EXPOSE 57902

ENV NAME=laimatt

# ENTRYPOINT ["./run.sh"]
CMD ["bash", "run.sh"]
