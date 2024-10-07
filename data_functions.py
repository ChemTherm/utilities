
from datetime import datetime

def write_device_informations(tk_obj, tfh_obj):
    
    # Keys to exclude from the output
    keys_to_exclude = ['x', 'y']

    # Open the file for writing
    with open(tk_obj.entries['SaveFile'], 'a') as file:
        # Write the header line with the current timestamp
        line = '### Device Informations at ' + datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f") + ':\n'
        file.write(line)

        # Loop through each device configuration
        for control_name, control_rule in tfh_obj.config.items():
            # Create a copy of the configuration and remove the keys to exclude
            filtered_control_rule = {k: v for k, v in control_rule.items() if k not in keys_to_exclude}

            # Write the filtered configuration to the file
            file.write(f"{control_name}: {filtered_control_rule}\n")