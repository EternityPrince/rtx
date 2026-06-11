import pytest
from pathlib import Path
from rtx.tui import RtxApp

@pytest.mark.asyncio
async def test_tui_startup_and_bindings(sandbox_dir):
    # Initialize the app on sandbox_dir
    app = RtxApp(sandbox_dir)
    
    # run_test runs the app headlessly for simulation
    async with app.run_test() as pilot:
        # Verify app configuration state
        assert app.project_path == sandbox_dir.resolve()
        assert len(app.selected_paths) == 0
        assert app.mirror_mode is False
        
        # Verify core UI layout elements exist
        assert app.query_one("#dir_tree") is not None
        assert app.query_one("#details_panel") is not None
        assert app.query_one("#output_path_input") is not None
        
        # Simulate pressing 'm' to toggle mirror/stream mode
        await pilot.press("m")
        assert app.mirror_mode is True
        
        # Simulate pressing 'm' again to revert
        await pilot.press("m")
        assert app.mirror_mode is False
        
        # Quit the app
        await pilot.press("q")
