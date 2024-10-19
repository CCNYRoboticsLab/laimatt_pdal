# Use an official Python runtime as a parent image
FROM pdal/pdal

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies
RUN apt-get update   

RUN chmod +x run.sh

RUN conda env create -f environment_cors.yml

RUN conda env create -f environment_visinspect.yml

RUN echo "source activate pdal_env" > ~/.bashrc
ENV PATH=/opt/conda/envs/pdal_env/bin:$PATH

EXPOSE 57902

ENV NAME=laimatt

# ENTRYPOINT ["./run.sh"]
CMD ["bash", "run.sh"]
