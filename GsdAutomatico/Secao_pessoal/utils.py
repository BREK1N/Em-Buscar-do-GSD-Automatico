RANK_HIERARCHY = {
    'CL': 0, 'TC': 1, 'MJ': 2, 'CP': 3, '1T': 4, '2T': 5, 'ASP': 6,
    'SO': 7, '1S': 8, '2S': 9, '3S': 10, 'CB': 11, 'S1': 12, 'S2': 13,
    'T1': 99, 'T2': 99, # Assuming Taifeiros have a low rank, adjust if necessary
}

def get_rank_value(posto_str):
    """
    Converts a 'posto' string into a numerical value for hierarchy comparison.
    Lower numbers represent higher ranks.
    """
    if not posto_str:
        return 999
    return RANK_HIERARCHY.get(posto_str.upper(), 99) # Default to a low rank if not found
