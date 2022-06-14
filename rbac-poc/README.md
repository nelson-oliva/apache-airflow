# AIRFLOW RBAC permissions
This POC demonstrate how Cloud Composer administrators can restrict access permissions at the DAG and UI level within Airflow by leveraging the RBAC built-in functionality. The first step is to use Cloud IAM to restrict access to the Cloud Composer environment and then go granular (DAG and UI level) with Airflow RBAC.

## Cloud Composer Environment Creation
First ensure that the Cloud Composer API is enabled IN Google Cloud Platform. You can check that by going to the "API & Services" menu and then by accessing to the "Enabled API and Services" submenu. If it's not enabled, you can quickly enable it in the console by looking for the "Cloud Composer API" service and clicking on the "Enable API" button or through the cloud shell with the following command:

```bash
gcloud services enable composer.googleapis.com
```

In case you have a Composer environment already created, skip this step, if not, in order to create one, you can quickly do so by executing the following commands.

<u>Note</u>: because Cloud Composer 2 uses Workload Identity, the service account of your environment must have bindings to the Kubernetes service account that runs your environment's cluster. As part of the commands exeecution below we add the role roles/composer.ServiceAgentV2Ext to the default Cloud Composer service account.

```bash

export LOCATION=us-central1
export PROJECT=<project id>
export IMAGE_VERSION=composer-2.0.14-airflow-2.2.3
export ENVIRONMENT_SIZE=small

gcloud projects add-iam-policy-binding fresh-sequence-351813 \
--member serviceAccount:service-962595729151@cloudcomposer-accounts.iam.gserviceaccount.com \
--role roles/composer.ServiceAgentV2Ext

gcloud composer environments create env-1 \
--location=${LOCATION} \
--image-version=${IMAGE_VERSION} \
--environment-size=${ENVIRONMENT_SIZE}
```

## POC Scenario Explanation

Two DAGS will be used in this POC:
- <b><u>DAG A</u></b>: a Bash Airflow Operator that prints a "Hello World! This is DAG-A".
- <b><u>DAG-B</u></b>: a Bash Airflow Operator that prints a "Hello World! This is DAG-B".

We will be creating two <u>roles</u>:
- <b><u>Consumers-Group-A</u></b>: which can just <b>view</b> DAG-A (Scenario 1).
- <b><u>Consumers-Group-B</u></b>: which can <b>view</b> DAG-B and also <b>execute</b> it (Scenario 2). This role will be updated (Scenario 3) to be able to also <b>view</b> (just view) DAG-A.

After having created the two DAGS and ROLES, we will be assigning these ROLES to different users to see the security restrictions applied at the DAG and UI level in action.

## DAGS import to Cloud Composer
- The 2 DAGS we will be using are stored in the following [folder](dags). Open the Cloud Shell and clone the GitHub repo by executing the following command:

```bash
git clone https://github.com/wcanetti/rbac-airflow.git
```

In order to upload the DAGS to the Cloud Composer DAGS folder, please execute the following command. Please first replace the <u>composer-environment-name</u> tag with the Cloud Composer environment name.

```bash
export ENVIRONMENT_NAME=<composer-environment-name>
gcloud composer environments storage dags import \
--environment ${ENVIRONMENT_NAME} \
--location ${LOCATION} \
--source="/home/${USER}/rbac-airflow/DAGs"
```

The Python script in this [folder](roles-creation-python-script) will allow an administrator to create or update airflow RBAC roles in order to add / restrict permissions to a Cloud Composer (Airflow) user.

As part of the parameters this Python script receives, you need too specify:
- Airflow URL (--airflow-url): the Airflow web UI URL.
- Role name (--role-name): the name of the role being created or updated.
- Access Token (--access-token): the access token used to securely connect to the Cloud Composer instance.
- DAGS (--dags): list of comma separated values with the name of the DAGS you want to apply the specified permissions.
- Priviligies (--privilegies): specify "read" for read permissions, specify "edit" for edit permissions, specify "delete" for delete permissions, specify "create" for create and specify "menu" for menu permissions.

<u>Note</u>: each GCP user is created in Cloud Composer with the "Op" Airflow role by default, which in terms of DAGS, gives you the ability to view, create and delete. In order to prevent this role assignment by default, as part of your IAC code you can include initialization scripts to override this behavior. For this POC, we will run the following command to remove the "Op" Airflow role to the users employed. Do not forget to update the \<project id\> and the \<user\> tag.

```bash
gcloud composer environments run ${ENVIRONMENT_NAME} \
--location ${LOCATION} \
--project ${PROJECT} \
users remove-role -- -e <user> -r Op
```

## RBAC role creation and user binding

### Scenario 1

By executing the command below we will be creating a role called <b>Consumers-Group-A</b> which will provide users having it with <b><u>read</u></b> permissions on the DAGs specified in the DAG list. In this case, DAG-A.

```bash
airflow_url=$(echo $(gcloud composer environments describe ${ENVIRONMENT} \
--location ${LOCATION} \
--project ${PROJECT} | grep airflowUri | awk '{ print $2}'))
role_name="Consumers-Group-A"
dag_list="DAG-A"
token=$(echo $(gcloud auth print-access-token))
privileges="read"

python3 /home/${USER}/rbac-airflow/roles-creation-python-script/airflow_rbac_roles.py \
-u $airflow_url -r $role_name -t $token -d $dag_list -p $privileges
```

Now, let's assign it to the user. Replace the \<user\> tag with the username you want to bind this role to.

```bash
gcloud composer environments run ${ENVIRONMENT} \ 
--location ${LOCATION} \ 
--project ${PROJECT} \ 
users add-role -- -e <user> -r Consumers-Group-A
```

The result in Cloud Composer should be the one depicted below, having DAG-A greyed out (only able to read/view):

![Scenario 1](images/dag-a.png)

### Scenario 2

By executing the command below we will be creating a role called <b>Consumers-Group-B</b> which will provide users having it with <b><u>read and execute</u></b> permissions on the DAGs specified in the DAG list. In this case, DAG-B.

```bash
airflow_url=$(echo $(gcloud composer environments describe ${ENVIRONMENT} \
--location ${LOCATION} \
--project ${PROJECT} | grep airflowUri | awk '{ print $2}'))
role_name="Consumers-Group-B"
dag_list="DAG-B"
token=$(echo $(gcloud auth print-access-token))
privileges="read edit create delete menu"

python3 /home/${USER}/rbac-airflow/roles-creation-python-script/airflow_rbac_roles.py \
-u $airflow_url -r $role_name -t $token -d $dag_list -p $privileges
```

Now, let's assign it to the user. Replace the \<user\> tag with the username you want to bind this role to.

```bash
gcloud composer environments run ${ENVIRONMENT} \ 
--location ${LOCATION} \ 
--project ${PROJECT} \ 
users add-role -- -e <user> -r Consumers-Group-B
```

The result in Cloud Composer should be the one depicted below, having DAG-B enabled, being able to read and execute:

![Scenario 2](images/dag-b.png)

### Scenario 3

Now, we will be <u>updating</u> the <b>Consumers-Group-B</b> by running the command again with the changes specified below. We will now specify DAG-A in the DAG list, and we will only provide <b><u>read</u></b> permissions for this specific DAG.

```bash
airflow_url=$(echo $(gcloud composer environments describe ${ENVIRONMENT} \
--location ${LOCATION} \
--project ${PROJECT} | grep airflowUri | awk '{ print $2}'))
role_name="Consumers-Group-B"
dag_list="DAG-A"
token=$(echo $(gcloud auth print-access-token))
privileges="read"

python3 /home/${USER}/rbac-airflow/roles-creation-python-script/airflow_rbac_roles.py \
-u $airflow_url -r $role_name -t $token -d $dag_list -p $privileges
```

The result in Cloud Composer should be the one depicted below, having DAG-A greyed out (only able to read/view), and having DAG-B enabled, being able to read and execute:

![Scenario 3](images/dag-a-b.png)
