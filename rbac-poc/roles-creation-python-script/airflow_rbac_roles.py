from typing import List
import requests
import argparse


def create_rbac_role_with_permissions(
        airflow_url: str,
        new_role_name: str,
        dag_names: List[str],
        privileges: List[str],
        google_access_token: str = None,
):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if google_access_token is not None:
        headers["Authorization"] = "Bearer " + google_access_token

    read = "can_read"
    edit = "can_edit"
    create = "can_create"
    delete = "can_delete"
    menu = "menu_access"

    # add general permissions
    permissions = []
    read_permissions = make_permissions(read,
                                        ["Task Instances", "Website", "DAG Runs", "Audit Logs", "ImportError", "XComs", \
                                         "DAG Code", "Plugins", "My Password", "My Profile", "Jobs", "SLA Misses",
                                         "DAG Dependencies", "Task Logs"])
    edit_permissions = make_permissions(edit, ["Task Instances", "My Password", "My Profile", "DAG Runs"])
    create_permissions = make_permissions(create, ["DAG Runs", "Task Instances"])
    delete_permissions = make_permissions(delete, ["DAG Runs", "Task Instances"])
    menu_permissions = make_permissions(menu, ["View Menus", "Browse", "Docs", "Documentation", "SLA Misses", "Jobs", \
                                               "DAG Runs", "Audit Logs", "Task Instances", "DAG Dependencies"])

    # permissions += read_permissions + edit_permissions + create_permissions + delete_permissions + menu_permissions
    if "read" in privileges:
        permissions += read_permissions
    if "edit" in privileges:
        permissions += edit_permissions
    if "delete" in privileges:
        permissions += delete_permissions
    if "create" in privileges:
        permissions += create_permissions
    if "menu" in privileges:
        permissions += menu_permissions

    # add dag-specific permissions
    prefix = "DAG:"
    dag_names = [prefix + dag for dag in dag_names]
    read_permissions += make_permissions(read, dag_names)
    edit_permissions += make_permissions(edit, dag_names)
    delete_permissions += make_permissions(delete, dag_names)

    if "read" in privileges:
        permissions += read_permissions
    if "edit" in privileges:
        permissions += edit_permissions
    if "delete" in privileges:
        permissions += delete_permissions

    data = {
        "actions": [
            *permissions
        ],
        "name": new_role_name
    }

    airflow_url += "/api/v1/roles"
    response = requests.post(airflow_url, json=data, headers=headers)

    if response.status_code == 403:
        raise PermissionError(
            f"Error 403 returned, please check if your AirFlow account is Op/Admin or verify the dags exist. \n {response.json()}")
    elif response.status_code == 401:
        raise PermissionError(
            f"Error 401 returned, please check the access token if the page is protected by an authentication")
    elif response.status_code == 409:
        print("Role with name {} already exist. Role will be updated".format(new_role_name))
        airflow_url += "/" + new_role_name
        response = requests.patch(airflow_url, json=data, headers=headers)
        if response.status_code == 200:
            print(f"Role `{new_role_name}` successfuly updated.")
        else:
            raise ConnectionError(f"An error occured during role updating: {response.json()}")
    elif response.status_code == 200:
        print(f"Role `{new_role_name}` successfuly created.")
    else:
        raise ConnectionError(f"An error occured during role creation: {response.json()}")


def make_permissions(action, resources):
    permissions = []
    for perm in resources:
        permissions.append(make_permission(action, perm))
    return permissions


def make_permission(action, resource):
    return {
        "action": {"name": action},
        "resource": {"name": resource}
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--airflow-url", required=True, help="URL to the composer Airflow UI root page")
    parser.add_argument("-r", "--role-name", required=True, help="Name of the new created role")
    parser.add_argument("-t", "--access-token", required=True,
                        help="Google access token used only if Airflow is managed by Cloud Composer")
    parser.add_argument("-d", "--dags", nargs="+", required=True, help="List of accessible dags for the role")
    parser.add_argument("-p", "--privileges", nargs="+", required=True,
                        help="List of dags permissions to be granted [read,edit,delete,create,menu]")

    args = parser.parse_args()
    create_rbac_role_with_permissions(
        args.airflow_url,
        args.role_name,
        args.dags,
        args.privileges,
        args.access_token,
    )
