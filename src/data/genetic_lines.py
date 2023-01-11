import csv

def load_genetic_lines(line=None):
	lines = []
	with open("Jenett.2012.9.24.tsv") as file: # TODO: move this file and cache it
		tsv_file = csv.reader(file, delimiter="\t")
		for row in tsv_file:
			row[1] = row[1].split("_")[1]
			if line is None or line in row[1]:
				lines.append(row)
	return lines



