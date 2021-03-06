#!/usr/bin/env python

'''
CompareContours.py
Written by Jeff Berry on Jan 17 2011

purpose:
	Runs Mean Sum of Distances (MSD) measurements on two sets of 
	tongue traces and writes the results to the user-specified
	file
	
usage:
	python CompareContours.py

--------------------------------------------------
Modified by Jeff Berry on Feb 25 2011
reason:
	added support for unique tracer codes on .traced.txt files
'''

import os, subprocess, time
import pygtk
pygtk.require("2.0")
import gtk
import gtk.glade
from math import *
from numpy import *
import multiprocessing
import sys
import shutil

WorkQueue_ = multiprocessing.Queue()

class WorkThread(multiprocessing.Process):        
	def run(self):
		flag = 'ok'
		while (flag != 'stop'):
			args = WorkQueue_.get()
			if args == None:
				flag = 'stop'
			else:
				c1X = args[0]
				c1Y = args[1]
				c2X = args[2]
				c2Y = args[3]
				ind = args[4]
				TRIM = args[5]
				goldname = args[6]
				experimentalname = args[7]
				savepath = args[8]

				if (TRIM == True):
					# find the biggest min and the smallest max of both curves and set those as the endpoints
					minc1 = min(c1X)
					minc2 = min(c2X)
					minx = max([minc1, minc2])
					maxc1 = max(c1X)
					maxc2 = max(c2X)
					maxx = min([maxc1, maxc2])
					c1Xi = array(range(minx, maxx+1))
					c1Yi = interp(c1Xi, c1X, c1Y)
					c2Xi = c1Xi
					c2Yi = interp(c2Xi, c2X, c2Y)

				else:
					#interpolate the curves to individual pixels
					try:
						min(c1X)
					except:
						print "Problem with ", goldname
					try: 
						min(c2X)
					except:
						print "Problem with ", experimentalname
					c1Xi = array(arange(min(c1X), max(c1X)+1))
					c1Yi = interp(c1Xi, c1X, c1Y)
					c2Xi = array(arange(min(c2X), max(c2X)+1))
					c2Yi = interp(c2Xi, c2X, c2Y)

				#find all the inter-point distances
				d = zeros((len(c1Xi), len(c2Xi)))
				for j in range(len(c1Xi)):
					for k in range(len(c2Xi)):
						d[j,k] = sqrt((c1Xi[j]-c2Xi[k])**2 + (c1Yi[j]-c2Yi[k])**2)

				#find minumum dist for each point
				md0 = amin(d, axis=0)
				md1 = amin(d, axis=1)
				mean0 = mean(md0)
				mean1 = mean(md1)
				md = mean([mean0, mean1])
				o = open(os.path.join(savepath,"{idx}.txt".format(idx=ind)), 'w')
				o.write('%06d,%s,%s,%.8f\n' % (ind, goldname, experimentalname, md))
				o.close()
				trace_name = self.commonsubstr(os.path.basename(goldname), os.path.basename(experimentalname))
				print "{trname}:\t{msd}".format(trname=trace_name, msd=md)

	def commonsubstr(self, t1, t2):
		name = ''
		for i in range(len(t1)):
			if t1[i] == t2[i]:
				name += t1[i]
			else:
				return name[:-1] if name[-1] in ".,/" else name

class CompareWindow:
	def __init__(self):
		gladefile = 'Compare.glade'
		self.wTree = gtk.glade.XML(gladefile, "window1")
		self.win = self.wTree.get_widget("window1")
		self.win.set_title("Compare Contours")
		
		dic  = {"on_window1_destroy" : sys.exit,
				"on_open1_clicked" : self.getgolddir,
				"on_open2_clicked" : self.getexperimentaldir,
				"on_open3_clicked" : self.getsavedir,
				"on_checkbutton1_toggled" : self.setTrim,
				"on_button1_clicked" : self.onStart}
		self.wTree.signal_autoconnect(dic)
		
		self.TRIM = False
		self.numGridlines = 32
		self.dir1entry = self.wTree.get_widget("entry1")
		self.dir2entry = self.wTree.get_widget("entry2")
		self.saveentry = self.wTree.get_widget("entry3")
		self.machineCBox = self.wTree.get_widget("combobox1")

		self.goldTraces = []
		self.experimentalTraces = []
		self.bad_traces = []
		self.threshold = 5
		
	def getgolddir(self, event):
		fc = gtk.FileChooserDialog(title='Open Trace Directory', parent=None, 
			action=gtk.FILE_CHOOSER_ACTION_OPEN, 
			buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
			gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		g_directory = fc.get_current_folder() if fc.get_current_folder() else os.path.expanduser("~")
		fc.set_current_folder(g_directory)
		fc.set_default_response(gtk.RESPONSE_OK)
		fc.set_select_multiple(True)
		ffilter = gtk.FileFilter()
		ffilter.set_name('Trace files')
		ffilter.add_pattern('*.traced.txt')
		fc.add_filter(ffilter)
		response = fc.run()
		if response == gtk.RESPONSE_OK:
			self.goldTraces = fc.get_filenames()
			g_directory = fc.get_current_folder()
			self.dir1entry.set_text(g_directory)
		fc.destroy()

	def getexperimentaldir(self, event):
		fc = gtk.FileChooserDialog(title='Open Trace Directory', parent=None, 
			action=gtk.FILE_CHOOSER_ACTION_OPEN, 
			buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
			gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		g_directory = fc.get_current_folder() if fc.get_current_folder() else os.path.expanduser("~")
		fc.set_current_folder(g_directory)
		fc.set_default_response(gtk.RESPONSE_OK)
		fc.set_select_multiple(True)
		ffilter = gtk.FileFilter()
		ffilter.set_name('Trace files')
		ffilter.add_pattern('*.traced.txt')
		fc.add_filter(ffilter)
		response = fc.run()
		if response == gtk.RESPONSE_OK:
			self.experimentalTraces = fc.get_filenames()
			g_directory = fc.get_current_folder()
			self.dir2entry.set_text(g_directory)
		fc.destroy()    
		
	def getsavedir(self, event):
		fc = gtk.FileChooserDialog(title='Save Results...', parent=None, 
			action=gtk.FILE_CHOOSER_ACTION_SAVE, 
			buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
			gtk.STOCK_SAVE, gtk.RESPONSE_OK))
		g_directory = fc.get_current_folder() if fc.get_current_folder() else os.path.expanduser("~")
		fc.set_current_folder(g_directory)
		fc.set_default_response(gtk.RESPONSE_OK)
		fc.set_do_overwrite_confirmation(True)

		response = fc.run()
		if response == gtk.RESPONSE_OK:
			self.savename = fc.get_filename()
			g_directory = fc.get_current_folder()
			self.saveentry.set_text(self.savename)
		fc.destroy()    
	  
	def setTrim(self, event):
		if self.TRIM == False:
			self.TRIM = True
		else:
			self.TRIM = False
	
	def checklists(self):
		'''Checks to make sure that both lists have the same items'''
		count = 0
		gold = []
		experimental = []
		for i in self.goldTraces:
			gold.append( (i.split('/')[-1]).split('.')[0] )
		for i in self.experimentalTraces:
			experimental.append( (i.split('/')[-1]).split('.')[0] )
		for i in trace1:
			if i not in experimental:
				count += 1
				print i + " is not in experimental"
		for i in experimental:
			if i not in gold:
				count += 1
				print i + " is not in gold"
		if count > 0:
			print str(count) + " missing traces"
		else:
			print "no missing traces"
		return count


	def checkInterp(self):
		'''Checks to see if the Contours have been interpolated to 32 points and does the interpolation if not'''
		alltraces = self.goldTraces
		for i in self.experimentalTraces:
			alltraces.append(i)
		for i in range(len(alltraces)):
			f = open(alltraces[i]).readlines()
			if (f[0][0:2] != '-1'):
				new = self.interpTrace(alltraces[i])
				if len(new) > 0:
					o = open(alltraces[i], 'w')
					for i in range(self.numGridlines):
						if new[i][0] != -1.:
							o.write("%d\t%.2f\t%.2f\n" % (i+1, new[i][0], new[i][1]))
						else:
							o.write("%d\t%d\t%d\n" % (-1, -1, -1))
					o.close()
				
	def interpTrace(self, filename):
		'''maps the existing trace onto the 32 line grid to produce a 32 point trace (or numGridlines)'''
		self.make_grid()
		
		# http://stackoverflow.com/questions/563198/how-do-you-detect-where-two-line-segments-intersect
		autotrace = open(filename, 'r').readlines()
		output_trace = []
		for i in range(self.numGridlines):
			output_trace.append(array([-1., -1.]))
		input_trace = []
		for i in range(len(autotrace)):
			x = autotrace[i][:-1].split('\t')
			if x[0] != '-1':
				input_trace.append(array([float(x[1]), float(x[2])]))

		# check whether we have any data
		if len(input_trace) == 0:
			return output_trace

		else:
			#determine whether each gridline intersects the trace
			minx = input_trace[0][0]
			maxx = input_trace[-1][0]

			for i in range(len(self.grid_values)):
				gridline = self.grid_values[i]
				leftedge = min(gridline[0],gridline[2])-20
				rightedge = max(gridline[0],gridline[2])+20

				segs = []
				for j in input_trace:
					if (j[0] >= leftedge) and (j[0] <= rightedge):
						#print i, leftedge, rightedge, j
						segs.append(j)

				if len(segs) > 0:
					for k in range(len(segs)-1):
						C = segs[k]
						D = segs[k+1]
						A = array([ gridline[0], gridline[1] ])
						B = array([ gridline[2], gridline[3] ])
						E = array([ B[0]-A[0], B[1]-A[1] ])
						F = array([ D[0]-C[0], D[1]-C[1] ])
						P = ( -E[1], E[0] )
						h = ( vdot((A-C), P) / vdot(F, P) )

						if (h >= 0) and (h <= 1):
							intersection = C + F*h
				try:
					output_trace[i] = intersection
					intersection = array([-1.,-1.])
				except:
					pass
			return output_trace

				
	def make_grid(self):
		'''makes the gridlines for interpolation of the raw traces from AutoTracer. 
			It has the option of which default grid to use, based on self.machine, 
			which is set by the user. New defaults should be added below to 
			machineOptions. The names of the options are set in the glade file, but this
			could be done in code too.
		'''
		# http://www.topcoder.com/tc?module=Static&d1=tutorials&d2=geometry2
		# See Adam Baker's experiment.cpp
		# Find Intersection of Lgridline and Rgridline
		# Lgridline standard form Ax + By = C
		
		#machineOptions is a dictionary that contains the leftmost and rightmost lines of the grid for each machine
		#specified in the machine combobox
		machineOptions = {'Sonosite Titan' : [[115., 167., 357., 392.], [421., 172., 667., 392.]],
						  'Toshiba' : [[155., 187., 286., 437.], [432., 187., 575., 437.]]}
						  
		self.leftpoints = array(machineOptions[self.machine][0]) 
		self.rightpoints = array(machineOptions[self.machine][1])

		Al = self.leftpoints[3] - self.leftpoints[1]
		Bl = self.leftpoints[0] - self.leftpoints[2]
		Cl = (Al*self.leftpoints[0]) + (Bl*self.leftpoints[1])
		
		#For some reason y1 and y2 are switched in the call to get_bounds()! (a bug in gnomecanvas?)
		tmp = self.rightpoints[1]
		self.rightpoints[1] = self.rightpoints[3]
		self.rightpoints[3] = tmp

		Ar = self.rightpoints[3] - self.rightpoints[1]
		Br = self.rightpoints[0] - self.rightpoints[2]
		Cr = (Ar*self.rightpoints[0]) + (Br*self.rightpoints[1])

		det = (Al*Br) - (Ar*Bl)

		if det == 0: #this needs to be fixed
			print "Lines are parallel -- try again"
		else:
			intx = ((Br*Cl) - (Bl*Cr))/det
			inty = ((Al*Cr) - (Ar*Cl))/det
			#print "intersection ", intx, inty
			A = array([intx, inty])
			B = array([self.leftpoints[0], self.leftpoints[1]])
			C = array([self.rightpoints[0], self.rightpoints[1]])
			D = array([self.leftpoints[2], self.leftpoints[3]])
			E = array([self.rightpoints[2], self.rightpoints[3]])

			AB = B - A
			AC = C - A
			AD = D - A
			AE = E - A

			angle_AB_horizontal = atan2(AB[1], AB[0])
			angle_AC_horizontal = atan2(AC[1], AC[0])

			linelength = linalg.norm(A-B)
			nearlength = linalg.norm(A-D)

			stepAngle = (angle_AB_horizontal - angle_AC_horizontal)/(self.numGridlines-1)

			self.grid_values = []
			for i in range(self.numGridlines):
				tmpAngle = angle_AB_horizontal-(i*stepAngle)
				tmpX = A[0] + round(linelength * cos(tmpAngle))
				tmpY = A[1] + round(linelength * sin(tmpAngle))

				tmpNearX = A[0] + round(nearlength * cos(tmpAngle))
				tmpNearY = A[1] + round(nearlength * sin(tmpAngle))

				self.grid_values.append(array([tmpNearX, tmpNearY, tmpX, tmpY]))

	def loadContours(self, traces):
		'''returns a list of arrays containing the non-empty points of the traces'''
		X = []
		Y = []
		for f in traces:
			lines = open(f, 'r').readlines()
			thisx = []
			thisy = []
			for l in lines:
				p = l[:-1].split('\t')
				if p[0] != '-1':
					thisx.append(float(p[1]))
					thisy.append(float(p[2]))
			X.append(array(thisx))
			Y.append(array(thisy))
		return X, Y
	
	def filtertraces(self, gold=None, experimental=None):
		"""
		make sure we don't have any entirely empty traces
		"""
		print "filtering traces..."
		new_gold = []
		new_experimental = []
		if not gold:
			gold = self.goldTraces
		if not experimental:
			experimental = self.experimentalTraces

		for i in range(len(gold)):
			if all([int(l.split("\t")[0]) == -1 for l in open(gold[i], 'r').readlines()]):
				self.bad_traces.append(gold[i])
			else:
				new_gold.append(gold[i])
				new_experimental.append(experimental[i])

		self.goldTraces = new_gold
		self.experimentalTraces = new_experimental
		print "removed {0} empty traces from consideration...".format(len(self.bad_traces))

	def problem_traces(self):
		"""
		move problem traces to folder for retracing/retraining
		"""
		pathtosave = os.path.dirname(self.savename)
		problem_traces_dir = os.path.join(pathtosave, "PROBLEM_TRACES_MSDge{0}".format(self.threshold))
		
		if os.path.exists(problem_traces_dir):
			shutil.rmtree(problem_traces_dir)
		os.mkdir(problem_traces_dir)

		print "flagged {0} problem traces for retracing...".format(len(self.bad_traces))
		for f in self.bad_traces:
			dst = os.path.join(problem_traces_dir, os.path.basename(f))
			#print "copying {0} to {1}".format(f, dst)
			shutil.copy(f, dst)

	def onStart(self, event):
		'''this is basically the main function that ties everything together'''
		model = self.machineCBox.get_model()
		index = self.machineCBox.get_active()
		self.machine = model[index][0]
		# this was to check whether the items in both lists had the same filenames, but with
		# the FileRenamer, this will not work. So the user has to make sure that the right items
		# are being compared.
		#missing = self.checklists()
		# instead, we'll just do a simple check to make sure both lists are the same length
		if (len(self.goldTraces) != len(self.experimentalTraces)):
			md = gtk.MessageDialog(None, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR,
				gtk.BUTTONS_CLOSE, "Error: The lists are not equal length")
			md.run()
			md.destroy()
			sys.exit(1)

		print "checking interpolation"
		
		#toss out completely empty traces here...
		print "gold traces before filtering: {0}".format(len(self.goldTraces))
		self.filtertraces()
		print "gold traces after filtering: {0}".format(len(self.goldTraces))

		self.checkInterp()
		c1X, c1Y = self.loadContours(self.goldTraces)
		c2X, c2Y = self.loadContours(self.experimentalTraces)
		pathtosave = os.path.dirname(self.savename)
		#print "Savename: {0}".format(self.savename)
		#print "path to save: {0}".format(pathtosave)
		tmpdir = os.path.join(pathtosave, 'ccTMP')
		#print "tmpdir: {0}".format(tmpdir)
		if os.path.exists(tmpdir):
			shutil.rmtree(tmpdir)
		os.mkdir(tmpdir)
		
		numThreads = 20
		for t in range(numThreads):
			thread = WorkThread()
			thread.start()
		
		for i in range(len(c2X)):  #self.goldTraces ended up getting c2Traces added to the end in checkInterp()
			WorkQueue_.put([c1X[i], c1Y[i], c2X[i], c2Y[i], i, self.TRIM, self.goldTraces[i], self.experimentalTraces[i], tmpdir])
			
		for t in range(numThreads):
			WorkQueue_.put(None)
		
		# wait for all threads to finish
		done = False
		while not done:
			p1 = subprocess.Popen(['ps', '-ef'], stdout=subprocess.PIPE)
			p2 = subprocess.Popen(['grep', '-i', 'CompareContours'], stdin=p1.stdout, stdout=subprocess.PIPE)
			p3 = subprocess.Popen(['wc', '-l'], stdin=p2.stdout, stdout=subprocess.PIPE)
			numproc = p3.communicate()[0]
			if (int(numproc)>1):
				time.sleep(1)
			else:
				done = True
		
		# collect the results
		files = os.listdir(tmpdir)
		o = open(self.savename, 'w')
		lines = []
		total = []
		for i in files:
			f = open(os.path.join(tmpdir, i), 'r').readlines()
			lines.append(f[0][:-1])
			d = float(f[0][:-1].split(',')[-1])
			if d > self.threshold:
				problem_trace = f[0][:-1].split(',')[1]
				self.bad_traces.append(problem_trace)
			total.append(d)
		for i in sorted(lines):
			o.write(i+'\n')
		o.write("mean: %.4f\n" % mean(total))    
		o.close()
		print "mean:", mean(total)
		
		#cleanup
		shutil.rmtree(tmpdir)
		self.problem_traces()
		sys.exit(0)
			
				
if __name__ == "__main__":
	CompareWindow()
	gtk.main()
