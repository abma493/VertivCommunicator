from time import sleep
from os import system
from threading import Thread, Lock, Condition
from queue import Queue, Empty
import multiprocessing as mp
from multiprocessing import Process

default_timeout = 15000
mini_wait = 5
current_mode: str = "Single (Default)"
path_to_batch = ""
path_to_config = ""
