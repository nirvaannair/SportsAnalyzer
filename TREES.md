PS C:\Users\Nirvaan\Desktop\SportsAnalyzer> cd backend
PS C:\Users\Nirvaan\Desktop\SportsAnalyzer\backend> tree /f
Folder PATH listing for volume Acer
Volume serial number is 0000007A 1C73:F0B8
C:.
│   __init__.py
│   
├───alembic
│   │   env.py
│   │   script.py.mako
│   │   
│   ├───versions
│   │   │   2d41504314b8_change.py
│   │   │   96075e0f1804_create_odds_snapshots_table.py
│   │   │   add_leg_status_to_bet_legs.py
│   │   │   b6fee8591550_fix_market_template_uniqueness.py
│   │   │   create_bet_legs_table.py
│   │   │   e51da8497d5f_create_core_tables.py
│   │   │   
│   │   └───__pycache__
│   │           002_create_core_tables.cpython-312.pyc
│   │           2d41504314b8_change.cpython-312.pyc
│   │           96075e0f1804_create_odds_snapshots_table.cpython-312.pyc
│   │           add_leg_status_to_bet_legs.cpython-312.pyc
│   │           b6fee8591550_fix_market_template_uniqueness.cpython-312.pyc
│   │           create_bet_legs_table.cpython-312.pyc
│   │           e51da8497d5f_create_core_tables.cpython-312.pyc
│   │           
│   └───__pycache__
│           env.cpython-312.pyc
│           
├───app
│   │   main.py
│   │   
│   ├───api
│   │   └───routes
│   │           analysis.py
│   │           bets.py
│   │           bet_slips.py
│   │           matches.py
│   │           settings.py
│   │           stake.py
│   │           websocket.py
│   │           
│   ├───core
│   │       config.py
│   │       database.py
│   │       security.py
│   │       
│   ├───database
│   │   ├───models
│   │   │       bet_slip.py
│   │   │       match.py
│   │   │       odds.py
│   │   │       placed_bet.py
│   │   │       prediction.py
│   │   │       team.py
│   │   │       
│   │   └───repositories
│   │           bet_slip_repository.py
│   │           match_repository.py
│   │           odds_repository.py
│   │           prediction_repository.py
│   │           
│   ├───integrations
│   │   ├───fbref
│   │   │       client.py
│   │   │       
│   │   ├───footystats
│   │   │       client.py
│   │   │       
│   │   ├───odds_api
│   │   │       client.py
│   │   │       
│   │   ├───stake
│   │   │       client.py
│   │   │       
│   │   ├───understat
│   │   │       client.py
│   │   │       
│   │   └───whoscored
│   │           client.py
│   │           
│   ├───schemas
│   │       bet_slip.py
│   │       match.py
│   │       prediction.py
│   │       settings.py
│   │       
│   ├───services
│   │   ├───analysis
│   │   │       analysis_service.py
│   │   │       match_ranking_service.py
│   │   │       
│   │   ├───bankroll
│   │   │       bankroll_service.py
│   │   │       
│   │   ├───cache
│   │   │       cache_service.py
│   │   │       
│   │   ├───football
│   │   ├───matches
│   │   │       match_service.py
│   │   │       
│   │   ├───odds
│   │   │       odds_service.py
│   │   │       
│   │   ├───slip_builder
│   │   │       slip_builder_service.py
│   │   │       slip_optimizer.py
│   │   │       substitution_service.py
│   │   │       
│   │   └───stake
│   │           stake_betting_service.py
│   │           stake_service.py
│   │           
│   ├───tasks
│   │       refresh_matches.py
│   │       refresh_odds.py
│   │       
│   ├───utils
│   │       datetime_utils.py
│   │       odds_utils.py
│   │       probability_utils.py
│   │       
│   ├───websocket
│   │       connection_manager.py
│   │       
│   └───workers
│           match_analysis_worker.py
│           slip_generation_worker.py
│           
├───database
│   │   base.py
│   │   session.py
│   │   __init__.py
│   │   
│   ├───models
│   │   │   betslip.py
│   │   │   bet_history.py
│   │   │   bet_leg.py
│   │   │   fixture.py
│   │   │   market.py
│   │   │   market_group.py
│   │   │   market_template.py
│   │   │   odds_snapshot.py
│   │   │   outcome.py
│   │   │   prediction.py
│   │   │   sport.py
│   │   │   tournament.py
│   │   │   __all_models.py
│   │   │   __init__.py
│   │   │   
│   │   └───__pycache__
│   │           betslip.cpython-312.pyc
│   │           bet_history.cpython-312.pyc
│   │           bet_leg.cpython-312.pyc
│   │           fixture.cpython-312.pyc
│   │           market.cpython-312.pyc
│   │           market_group.cpython-312.pyc
│   │           market_template.cpython-312.pyc
│   │           odds_snapshot.cpython-312.pyc
│   │           outcome.cpython-312.pyc
│   │           prediction.cpython-312.pyc
│   │           sport.cpython-312.pyc
│   │           tournament.cpython-312.pyc
│   │           __all_models.cpython-312.pyc
│   │           __init__.cpython-312.pyc
│   │           
│   └───__pycache__
│           base.cpython-312.pyc
│           session.cpython-312.pyc
│           __init__.cpython-312.pyc
│           
├───integrations
│   ├───football
│   │       fbref_client.py
│   │       footystats_client.py
│   │       odds_api_client.py
│   │       understat_client.py
│   │       __init__.py
│   │       
│   └───stake
│       │   balance_service.py
│       │   bet_history_service.py
│       │   bet_placement_service.py
│       │   fixture_market_service.py
│       │   fixture_service.py
│       │   graphql_client.py
│       │   main_market_service.py
│       │   market_service.py
│       │   models.py
│       │   odds_service.py
│       │   queries.py
│       │   __init__.py
│       │   
│       └───__pycache__
│               bet_history_service.cpython-312.pyc
│               fixture_market_service.cpython-312.pyc
│               fixture_service.cpython-312.pyc
│               graphql_client.cpython-312.pyc
│               main_market_service.cpython-312.pyc
│               queries.cpython-312.pyc
│               __init__.cpython-312.pyc
│               
├───services
│   │   fixture_filter_service.py
│   │   market_line_parser.py
│   │   odds_snapshot_service.py
│   │   odds_snapshot_sync_service.py
│   │   stake_bet_history_sync_service.py
│   │   stake_fixture_sync_service.py
│   │   stake_main_market_sync_service.py
│   │   stake_market_sync_service.py
│   │   
│   └───__pycache__
│           odds_snapshot_service.cpython-312.pyc
│           stake_bet_history_sync_service.cpython-312.pyc
│           stake_fixture_sync_service.cpython-312.pyc
│           stake_main_market_sync_service.cpython-312.pyc
│           
├───sql
│       001_create_matches.sql
│       002_create_teams.sql
│       003_create_odds.sql
│       004_create_predictions.sql
│       005_create_bet_slips.sql
│       006_create_bet_slip_legs.sql
│       007_create_placed_bets.sql
│       008_create_bankroll_snapshots.sql
│       009_create_model_runs.sql
│       010_create_analysis_jobs.sql
│       011_create_team_ratings.sql
│       012_create_feature_cache.sql
│       
├───tests
│       test_analysis.py
│       test_matches.py
│       test_slip_builder.py
│       
└───__pycache__
        __init__.cpython-312.pyc




PS C:\Users\Nirvaan\Desktop\SportsAnalyzer\scripts> tree /f
Folder PATH listing for volume Acer
Volume serial number is 00000073 1C73:F0B8
C:.
    explore_stake_api.py
    reset_database.ps1
    run_fixture_sync_loop.py
    setup.ps1
    start_all.ps1
    start_backend.ps1
    start_frontend.ps1
    start_ml_service.ps1
    sync_bet_history.py
    sync_stake_fixtures.py
    sync_stake_main_markets.py
    sync_stake_markets.py
    test_bet_history.py
    test_fixture_ingestion.py
    test_fixture_main_markets.py
    test_odds_snapshot.py
    
No subfolders exist 

PS C:\Users\Nirvaan\Desktop\SportsAnalyzer\scripts> 





