"""Apply additive lab migrations with a direct Neon connection."""
from pathlib import Path
import argparse
import os

import psycopg
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', default='.env')
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    url = os.getenv('DATABASE_URL_DIRECT') or os.getenv('DATABASE_URL')
    if not url:
        raise SystemExit('Set DATABASE_URL_DIRECT in the selected environment file.')
    migrations = sorted((Path(__file__).resolve().parents[1] / 'database' / 'migrations').glob('*.sql'))
    with psycopg.connect(url, connect_timeout=10) as conn:
        conn.execute("SET LOCAL statement_timeout = '60000ms'")
        for migration in migrations:
            conn.execute(migration.read_text())
            print(f'Applied {migration.name}')
    print('Additive migrations complete.')


if __name__ == '__main__':
    main()
