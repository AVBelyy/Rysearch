import numpy as np
import numpy as np
import time


from itertools import permutations
import random
import time
import numpy as np
import os
from math import exp

import ctypes
from ctypes import c_int, c_double, POINTER, CDLL

 


class HamiltonPath:
	def __init__(self, adj, caller=None):
		self.A = adj
		if adj.shape[0] != adj.shape[1]:
			raise ValueError("Adjacency matrix should be square")
		self.N = adj.shape[0]		
		for i in range (0, self.N):
			if abs(self.A[i][i]) > 1e-6:
				raise ValueError ("Diagonal elements should be 0 ,but A[%d][%d]=%f" % (i,i,self.A[i][i]))
			self.A[i][i] = 0
			for j in range (i+1, self.N):
				if (self.A[i][j]!=self.A[j][i]):
					raise ValueError("Adjacency matrix should be symmetric")
		self.path = [i for i in range (0,self.N)]
		self.cut_branch = self.N
		self.atomic_iterations = 10000
		self.caller = caller
		self.clusters = [self.N]
		self.DEBUG = False		# If True, will be used python implementation of annealing, which is 100 times slower, but yields graphs
		

	def solve(self):	
		if self.solve_lkh():
			return self.path
		raise Warning("LKH is not installed.")
		return self.path
		
	def solve_lkh(self):
		try:
			lkh_path = os.path.join("/Users/aksholokhov/Local Docs/repos/rysearch/experiments/LKH-2.0.7")
		except:
			lkh_path = os.path.join("/Users/aksholokhov/Local Docs/repos/rysearch/experiments/LKH-2.0.7")
		
		try:
			temp_folder = lkh_path
		except:
			temp_folder = lkh_path
		
		exe_path = os.path.join(lkh_path, "lkh")
		tsp_path = os.path.join(temp_folder, "hamilton.tsp")
		par_path = os.path.join(temp_folder, "hamilton.par")
		out_path = os.path.join(temp_folder, "hamilton.out")
		
		if not os.path.exists(exe_path):
			raise ImportWarning("%s"%exe_path)
			return False
		
		with open(tsp_path, "w") as f:
			f.write("TYPE : TSP\n")
			f.write("DIMENSION : %d\n" % (self.N+1))
			f.write("EDGE_WEIGHT_TYPE : EXPLICIT\n")
			f.write("EDGE_WEIGHT_FORMAT : FULL_MATRIX\n")
			f.write("EDGE_WEIGHT_SECTION\n")
			for i in range(self.N):
				for j in range(self.N):
					f.write("%d " % int(100000*self.A[i][j]))
				f.write("0\n")
			for j in range(self.N+1):
				f.write("0 ")
			f.write("\nEOF")	
		
		with open(par_path, "w") as f:
			f.write("PROBLEM_FILE = %s\n" % tsp_path)
			f.write("OUTPUT_TOUR_FILE = %s\n" % out_path)
			f.write("PRECISION = 1\n")
			f.write("TRACE_LEVEL = 0\n")
			
			
		start_time = time.time()	
		from subprocess import call
		call("cd \"%s\" && ./lkh \"%s\" < \"%s\""%(lkh_path, par_path, par_path), shell=True)
		
		
		fake_path = []
		line_ctr = -1
		for line in open(out_path, "r"):
			if line_ctr >=0 and line_ctr <= self.N:
				fake_path.append(int(line)-1)
				line_ctr += 1
			if "TOUR_SECTION" in line:
				line_ctr = 0
		
		sep = 0
		for i in range(self.N+1):
			if fake_path[i] == self.N:
				sep = i
		self.path = fake_path[sep+1:] + fake_path[0:sep]
		return self.path

		

def arrange_topics(phi):
	metric = hellinger
	phi_t = phi.transpose()
	N = phi.shape[1]
	topic_distances = np.zeros((N, N))		
	for i in range(N):
		for j in range(N):
			topic_distances[i][j] = metric(phi_t[i], phi_t[j])
	return get_arrangement_permutation(topic_distances, mode="hamilton")
	

def get_arrangement_permutation(dist, mode, model=None, clusters=None, init_perm=None):
	start_time = time.time()
	
	if mode == "none":
		return [i for i in range(dist.shape[0])] 
	if mode == "hamilton":
		hp = HamiltonPath(dist, caller=model)
		hp.solve()
		perm = hp.path
	return perm


def hellinger(p,q):
	_SQRT2 = np.sqrt(2)
	return np.linalg.norm(np.sqrt(p) - np.sqrt(q)) / _SQRT2