from common.common_imports import *
import configparser
from enum import Enum

def cfg_dat_parser(file_path: str) -> dict[str, list[tuple[str, str]]]:
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    first_line_i = None # find the first line with INI format [Type]
    for i, line in enumerate(lines):
        if line.strip().startswith('[') and line.strip().endswith(']'):
            first_line_i = i
            break
    
    if first_line_i is None:
        return {} # Bad config file
    
    ini_content = ''.join(lines[first_line_i:])

    try:
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read_string(ini_content)
    except Exception as e:
        Logger.log(f"An error has occured during parsing: {e}")

    sections = ['Time Service', 'Network.IPv4', 'Email Messaging']

    # dict comprehension
    return { section: list(config[section].items()) for section in sections if section in config }

