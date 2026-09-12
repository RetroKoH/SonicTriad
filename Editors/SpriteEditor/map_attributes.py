# In the future, additional user-defined formats will be possible
# For that reason, this is stored outside of the loading functions
MAP_FORMATS = {
	1: {
		'header_size': 1,
		'piece_size': 5,
		'attr_bytes': 2,
		'x_bytes': 1
	},
	2: {
		'header_size': 2,
		'piece_size': 8,
		'attr_bytes': 4,
		'x_bytes': 2
	},
	3: {
		'header_size': 2,
		'piece_size': 6,
		'attr_bytes': 2,
		'x_bytes': 2
	}
}