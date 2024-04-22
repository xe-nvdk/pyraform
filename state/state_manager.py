import json
import os

def load_state(file_path='state.json'):
    """Loads the current state from a JSON file."""
    if not os.path.exists(file_path):
        return {"resources": []}
    with open(file_path, 'r') as file:
        return json.load(file)

def save_state(state, file_path='state.json'):
    """Saves the state to a JSON file."""
    with open(file_path, 'w') as file:
        json.dump(state, file, indent=4)

def update_state(state, resource, action):
    """Updates the state based on an action (create, update, delete)."""
    if action == "create":
        state["resources"].append(resource)
    elif action == "update":
        for res in state["resources"]:
            if res["name"] == resource["name"] and res["type"] == resource["type"]:
                res["properties"] = resource["properties"]
    elif action == "delete":
        state["resources"] = [
            res for res in state["resources"] 
            if not (res["name"] == resource["name"] and res["type"] == resource["type"])
        ]
    save_state(state)
