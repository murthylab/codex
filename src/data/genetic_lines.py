import csv

def load_genetic_lines():
	lines = []
	with open("Jennet.2012.9.24.tsv") as file:
		tsv_file = csv.reader(file, delimiter="\t")
		for row in tsv_file:
			lines.append(row)
	return lines
