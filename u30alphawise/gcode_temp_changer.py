import os, sys, re, traceback

# accounts for the difference in input() between python2 and python3
try:
	input = raw_input
except NameError:
	pass


def getZ_slic3r(l):
	"""Slic3r"""
	rgx = r"(?<=^G1 Z)\d?\d?\d\.\d(?=[\dF\. ]*$)"
	match = re.search(rgx, l)
	return float(match.group(0)) if match else None

def getZ_cura(l):
	"""Cura"""
	# presence of F parameter depends on the version of cura engine
	# 2 stage regex required: pythons default regex engine can't handle repeaters in lookbehinds
	rgx1 = r"^G0 F?[\d ]*X[\.\d ]*Y[\.\d ]*Z[\.\d ]*"
	rgx2 = r"(?<=Z)\d{1,3}(.\d+)?"
	if re.search(rgx1, l):
		return float(re.search(rgx2, l).group(0))
	return None
	
def getZ_craftware(l):
	"""Craftware"""
	rgx1 = r"^G0 F[\d ]*Z[\.\d ]*"
	rgx2 = r"(?<=Z)\d{1,3}(.\d+)?"
	if re.search(rgx1, l):
		return float(re.search(rgx2, l).group(0))
	return None
	
slicers = [getZ_slic3r, getZ_cura, getZ_craftware]

def perform(filename):
	f = open(filename, 'r')
	lines = f.readlines()
	f.close()
	
	# test each helper method against the gcode
	tests = [len([l for l in lines if s(l)]) for s in slicers]
	if max(tests) == 0:
		print("\nThe slicer that generated your gcode isn't yet supported.")
		print("\nSend your gcode file to me so I can add it.")
		sys.exit()
	# assuming the user is using a sensible stl; un-recognised gcode coupled with
	# false-positives in their custom start/end sections is the hazard here	
	if 0 < max(tests) < 10:
		print("\nCould only detect a small amount of Z moves.")
		print("\nEither the slicer that generated your gcode isn't yet supported,")
		print("or the model you're using is exceptionally small.")
		sys.exit()
	
	# continue using the helper method that found the most matches
	getz = slicers[tests.index(max(tests))]
	last_zline = [l for l in lines if getz(l)][-1]
	height = getz(last_zline)
	
	print("Detected gcode from %s" % getz.__doc__)
	start_temp =     int(input("\nPlease enter the starting temperature                      : "))
	final_temp =     int(input(  "Please enter the final temperature                         : "))
	temp_steps = abs(int(input(  "Please enter the amount at which temperature should change : ")))

	if final_temp < start_temp:
		final_temp -= 2
		temp_steps = -temp_steps
	temps = list(range(start_temp, final_temp+1, temp_steps))
	temp_change_height = round(height/len(temps), 1)

	print("\nThe temp regions are [%s]." % ", ".join(map(str, temps)))
	print("\nGiven that the model is %.1f mm tall, with %d distinct temp regions" % (height, len(temps)))
	print("the temp will change every %.1f mm...\n" % temp_change_height)
	for i in range(0, len(temps)):
		print("%5.1f to %5.1f mm - %d degrees" % \
		(i*temp_change_height, height if i==len(temps)-1 else (i+1)*temp_change_height, temps[i]))
	
	print("\n")
	# set initial M109 and/or M104
	inserted_M109 = False
	inserted_M104 = False
	extra_M104 = []
	rgx = re.compile(r"(?<=M10(4|9) S)\d{1,3}(?=\b)|(?<=M10(4|9) T\d S)\d{1,3}(?=\b)")
	for lineNumber, l in enumerate(lines):
		if not inserted_M109 and l.startswith("M109"):
			target = rgx.search(l).group(0)
			if target != "0": # ignore any lines attempting to turn the extruder off
				#print("M109 found, line %d" % lineNumber)
				lines[lineNumber] = rgx.sub(str(start_temp), l)
				inserted_M109 = True
				continue
		if l.startswith("M104"):
			target = rgx.search(l).group(0)
			if target == "0":
				continue # ignore any lines attempting to turn the extruder off
			#print("M104 found, line %d" % lineNumber)
			if not inserted_M104: 
				lines[lineNumber] = rgx.sub(str(start_temp), l)
				inserted_M104 = True
			extra_M104.append( (lineNumber, l) ) 
	if not inserted_M109 and not inserted_M104:
		print("\nERROR: No M104 or M109 commands found, check your starting gcode. Aborting script...")
		sys.exit()
	if len(extra_M104) > 1:
		print("\nWARNING: There are more than two M104 commands already present in the gcode...")
		for lineNumber, l in extra_M104:
			print("  line %6d : %s" % (lineNumber, l.strip()) )
		print("\nThe first command on line %d will be changed to your starting temp of %d," % (extra_M104[0][0], start_temp))
		print("however the subsequent ones may effect your test.")
		var = input("\n...would you like to remove these extra commands before proceeding? y/n: ")
		if (var.lower()=='y'):
			extra_M104.pop(0)	# keep the first one
			for lineNumber, l in extra_M104:
				lines[lineNumber] = "; " + l
				print("  disabled line %6d : %s" % (lineNumber, l.strip()) )

	
	# loop through and insert the rest of the temp changes
	for i in range(1, len(temps)):
		z = i*temp_change_height
		t = "M104 S" + str(temps[i]) + "\n"
		for lineNumber, line in enumerate(lines):
			height = getz(line)
			if height is not None and height >= z:
				lines.insert(lineNumber, t)
				break

	newfile = filename.replace(".gcode", "_EDITED.gcode")
	f = open(newfile, 'w')
	f.writelines(lines)
	f.close()
	print('\nNew file created...\n"%s"\n' % newfile)
	

if __name__ == '__main__':
	if  len(sys.argv) != 2:
		print("To use this script you need to pass it a single gcode file.")
		print("Simply drag and drop your gcode file on to this script's icon")
		print("and then follow the prompts.")
	else:
		try:
			file = sys.argv[1]
			if not file.endswith(".gcode"):
				print("This script is for gcode files only.")
			else:
				perform(file)
		except ValueError:
			print("\nScript failed. You must enter a whole number.")
		except SystemExit:
			pass
		except:
			print("\nScript failed.\n")
			traceback.print_exc()
	input("\nPress any key to exit...")