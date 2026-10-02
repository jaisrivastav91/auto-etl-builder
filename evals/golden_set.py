GOLDEN = [
    {
        "name": "pokeapi", "base_url": "https://pokeapi.co/api/v2/",
        "endpoints": ["pokemon", "type"], "expect_tables": ["pokemon", "type"]
    },
    {
        "name": "restcountries", "base_url": "https://restcountries.com/v3.1/",
        "endpoints": ["all"], "expect_tables": ["all"]},
    {
        "name": "open_meteo", "base_url": "https://api.open-meteo.com/v1/",
        "endpoints": ["forecast"], "expect_tables": ["forecast"]
    },
]