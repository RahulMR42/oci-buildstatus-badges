import io
import os
import oci
import json
import string
import random
import logging

from fdk import response


class devops:
    def __init__(self,region):
        self.region = region
        self.signer = oci.auth.signers.get_resource_principals_signer()

    def copy_image(self,object_storage_client,namespace,bucket_name,status_icon,final_icon_filename):
        status_icon_content = object_storage_client.get_object(namespace,bucket_name,status_icon)
        file_tag = ''.join(random.choices(string.ascii_letters, k=7))
        file_name = f"/tmp/{file_tag}"

        with open(file_name, 'wb') as f:
            for chunk in status_icon_content.data.raw.stream(1024 * 1024, decode_content=False):
                f.write(chunk)

        with open(file_name, 'rb') as f:
            object_storage_client.put_object(namespace,bucket_name,final_icon_filename,f)


    def fetch_build_status(self,build_run_id):
        try:
            logging.getLogger().info("Fetch build informations")
            devops_client = oci.devops.DevopsClient(config={'region': self.region}, signer = self.signer)
            logging.getLogger().info('Initialized devops client')
            get_build_run_response = devops_client.get_build_run(
                build_run_id = build_run_id
            )
            build_run_status = get_build_run_response.data.lifecycle_state
            logging.getLogger().info(f"Response for the build run {build_run_id} is {str(build_run_status)}")
            namespace = os.environ['os_namespace']
            bucket_name = os.environ['os_bucketname']
            object_name = os.environ['os_objectname']
            object_storage_client = oci.object_storage.ObjectStorageClient(config={'region': self.region}, signer = self.signer)
            logging.getLogger().info('Initialized object storage client')
            obj_status_updates = object_storage_client.put_object(
                namespace,
                bucket_name,
                object_name,
                str(get_build_run_response.data))
            status_icon = os.environ['build_progress_image_name']
            final_icon_filename = os.environ['build_finalstatus_image_name']
            logging.getLogger().info('Updating in progress status')
            self.copy_image(object_storage_client,namespace,bucket_name,status_icon,final_icon_filename)
            if build_run_status == 'SUCCEEDED':
                status_icon = os.environ['build_ok_image_name']
            else:
                status_icon = os.environ['build_failed_image_name']
            logging.getLogger().info('Updating final status')
            self.copy_image(object_storage_client,namespace,bucket_name,status_icon,final_icon_filename)

            return build_run_status

        except Exception as error:
            logging.getLogger().error("Exception" + str(error))


def handler(ctx, data: io.BytesIO = None):
    try:
        body = json.loads(data.getvalue())
        logging.getLogger().info("Inside Build Stage function")
        build_run_ocid = body[0]['data']['buildRunId']
        logging.getLogger().info(f"Working on Build run id {build_run_ocid}")
        oci_region = os.environ['oci_region']
        devops_handler = devops(oci_region)
        devops_handler.fetch_build_status(build_run_ocid)
    except (Exception, ValueError) as ex:
        logging.getLogger().info('error parsing json payload: ' + str(ex))


    return response.Response(
        ctx, response_data=json.dumps(
            {"message": f"Function exec done for run id {build_run_ocid}"}),
        headers={"Content-Type": "application/json"}
    )