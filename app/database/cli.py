"""
Database management CLI utilities
"""
import asyncio
import logging
import sys
from typing import Optional
import click
from sqlalchemy import text
from app.core.database import engine, init_database, close_database, check_database_health
from app.database.migrations import migration_manager

logger = logging.getLogger(__name__)


@click.group()
def db():
    """Database management commands"""
    pass


@db.command()
def init():
    """Initialize database with tables and constraints"""
    click.echo("Initializing database...")
    
    async def _init():
        try:
            await init_database()
            click.echo("✅ Database initialized successfully")
        except Exception as e:
            click.echo(f"❌ Database initialization failed: {e}")
            sys.exit(1)
    
    asyncio.run(_init())


@db.command()
def health():
    """Check database health and connection status"""
    click.echo("Checking database health...")
    
    async def _health():
        try:
            status = await check_database_health()
            
            if status['status'] == 'healthy':
                click.echo("✅ Database is healthy")
                click.echo(f"   Connection: {status['connection']}")
                click.echo(f"   Tables: {len(status['existing_tables'])} found")
            else:
                click.echo(f"⚠️  Database status: {status['status']}")
                if 'missing_tables' in status and status['missing_tables']:
                    click.echo(f"   Missing tables: {', '.join(status['missing_tables'])}")
                if 'error' in status:
                    click.echo(f"   Error: {status['error']}")
                    
        except Exception as e:
            click.echo(f"❌ Health check failed: {e}")
            sys.exit(1)
    
    asyncio.run(_health())


@db.command()
@click.argument('migration_name')
def migrate(migration_name: str):
    """Run a specific migration"""
    click.echo(f"Running migration: {migration_name}")
    
    async def _migrate():
        try:
            success = await migration_manager.run_migration(migration_name)
            if success:
                click.echo(f"✅ Migration '{migration_name}' completed successfully")
            else:
                click.echo(f"❌ Migration '{migration_name}' failed")
                sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Migration failed: {e}")
            sys.exit(1)
    
    asyncio.run(_migrate())


@db.command()
def create_tables():
    """Create all database tables"""
    click.echo("Creating database tables...")
    
    async def _create():
        try:
            success = await migration_manager.create_tables()
            if success:
                click.echo("✅ Tables created successfully")
            else:
                click.echo("❌ Table creation failed")
                sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Table creation failed: {e}")
            sys.exit(1)
    
    asyncio.run(_create())


@db.command()
@click.option('--confirm', is_flag=True, help='Confirm the reset operation')
def reset(confirm: bool):
    """Reset database (drop and recreate all tables)"""
    if not confirm:
        click.echo("⚠️  This will drop all tables and data!")
        click.echo("Use --confirm flag to proceed")
        return
    
    click.echo("Resetting database...")
    
    async def _reset():
        try:
            # Drop all tables
            from app.core.database import Base
            Base.metadata.drop_all(bind=engine)
            click.echo("   Dropped all tables")
            
            # Recreate tables
            success = await migration_manager.create_tables()
            if success:
                click.echo("✅ Database reset successfully")
            else:
                click.echo("❌ Database reset failed")
                sys.exit(1)
                
        except Exception as e:
            click.echo(f"❌ Database reset failed: {e}")
            sys.exit(1)
    
    asyncio.run(_reset())


@db.command()
@click.argument('query')
def query(query: str):
    """Execute a raw SQL query"""
    click.echo(f"Executing query: {query}")
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            
            if result.returns_rows:
                rows = result.fetchall()
                if rows:
                    # Print column headers
                    columns = result.keys()
                    click.echo(" | ".join(columns))
                    click.echo("-" * (len(" | ".join(columns))))
                    
                    # Print rows
                    for row in rows:
                        click.echo(" | ".join(str(value) for value in row))
                else:
                    click.echo("No rows returned")
            else:
                click.echo(f"Query executed successfully. Rows affected: {result.rowcount}")
                
    except Exception as e:
        click.echo(f"❌ Query failed: {e}")
        sys.exit(1)


@db.command()
def cleanup():
    """Clean up expired conversation states and old data"""
    click.echo("Cleaning up old data...")
    
    async def _cleanup():
        try:
            # Clean up expired conversation states (older than 24 hours)
            with engine.connect() as conn:
                result = conn.execute(text("""
                    DELETE FROM conversation_states 
                    WHERE updated_at < NOW() - INTERVAL '24 hours'
                """))
                conn.commit()
                click.echo(f"   Cleaned up {result.rowcount} expired conversation states")
                
                # Clean up old payment requests (older than 30 days)
                result = conn.execute(text("""
                    DELETE FROM payment_requests 
                    WHERE created_at < NOW() - INTERVAL '30 days' 
                    AND status IN ('failed', 'confirmed')
                """))
                conn.commit()
                click.echo(f"   Cleaned up {result.rowcount} old payment requests")
                
            click.echo("✅ Cleanup completed successfully")
            
        except Exception as e:
            click.echo(f"❌ Cleanup failed: {e}")
            sys.exit(1)
    
    asyncio.run(_cleanup())


@db.command()
def validate():
    """Validate database schema and constraints"""
    click.echo("Validating database schema...")
    
    async def _validate():
        try:
            success = await migration_manager.run_migration('validate')
            if success:
                click.echo("✅ Database schema validation passed")
            else:
                click.echo("❌ Database schema validation failed")
                sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Validation failed: {e}")
            sys.exit(1)
    
    asyncio.run(_validate())


@db.command()
@click.option('--output', '-o', help='Output file for backup')
def backup():
    """Create a backup of database schema"""
    click.echo("Creating database schema backup...")
    
    async def _backup():
        try:
            backup_data = await migration_manager.backup_schema()
            if backup_data:
                import json
                from datetime import datetime
                
                output_file = f"schema_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                with open(output_file, 'w') as f:
                    json.dump(backup_data, f, indent=2, default=str)
                
                click.echo(f"✅ Schema backup saved to {output_file}")
            else:
                click.echo("❌ Failed to create schema backup")
                sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Backup failed: {e}")
            sys.exit(1)
    
    asyncio.run(_backup())


@db.command()
def stats():
    """Show database statistics"""
    click.echo("Gathering database statistics...")
    
    async def _stats():
        try:
            with engine.connect() as conn:
                # Get table row counts
                tables = ['users', 'contacts', 'bills', 'bill_participants', 'payment_requests', 'conversation_states']
                
                click.echo("\n📊 Table Statistics:")
                click.echo("-" * 40)
                
                for table in tables:
                    try:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()
                        click.echo(f"{table:20} | {count:>10} rows")
                    except Exception as e:
                        click.echo(f"{table:20} | Error: {e}")
                
                # Get recent activity
                click.echo("\n📈 Recent Activity (Last 24h):")
                click.echo("-" * 40)
                
                recent_bills = conn.execute(text("""
                    SELECT COUNT(*) FROM bills 
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)).scalar()
                
                recent_payments = conn.execute(text("""
                    SELECT COUNT(*) FROM payment_requests 
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)).scalar()
                
                click.echo(f"New bills:           {recent_bills}")
                click.echo(f"Payment requests:    {recent_payments}")
                
                # Get payment status distribution
                click.echo("\n💰 Payment Status Distribution:")
                click.echo("-" * 40)
                
                status_result = conn.execute(text("""
                    SELECT payment_status, COUNT(*) 
                    FROM bill_participants 
                    GROUP BY payment_status
                """))
                
                for status, count in status_result:
                    click.echo(f"{status:15} | {count:>10}")
                
        except Exception as e:
            click.echo(f"❌ Failed to gather statistics: {e}")
            sys.exit(1)
    
    asyncio.run(_stats())


if __name__ == '__main__':
    db()