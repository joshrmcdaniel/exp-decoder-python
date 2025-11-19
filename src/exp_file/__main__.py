import exp_file
import pathlib
import os
t =pathlib.Path(os.path.join("Episodes","Fourth_of_July_2010.exp"))
h = exp_file.decode_exp_file(t, pathlib.Path("output"))
