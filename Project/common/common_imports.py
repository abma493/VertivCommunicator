from time import sleep
import os
from threading import Thread, Lock, Condition
from queue import Queue, Empty
import multiprocessing as mp
from multiprocessing import Process

default_timeout = 15000
mini_wait = 5