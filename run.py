import asyncio
from harness.runtime import run_agent

if __name__ == "__main__":
    print(asyncio.run(run_agent("https://pokeapi.co/api/v2/", ["pokemon", "type"])))