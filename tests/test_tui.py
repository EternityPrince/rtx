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
        assert app.query_one("#preview_title") is not None
        assert app.query_one("#preview_content") is not None
        assert app.query_one("#preview_markdown") is not None
        assert app.query_one("#search_input") is not None
        assert app.query_one("#open_file_btn") is not None
        
        # Verify preview area is focusable
        assert app.query_one("#preview_content").can_focus is True
        
        # Test search input updates app search query
        app.query_one("#search_input").value = "*.py"
        await pilot.pause()
        assert app.search_query == "*.py"
        
        # Verify preview updates for a directory
        app.show_preview(sandbox_dir)
        for _ in range(50):
            await pilot.pause(0.05)
            if "Folder:" in str(app.query_one("#preview_content").content):
                break
        assert "Folder:" in str(app.query_one("#preview_content").content)
        assert app.query_one("#open_file_btn").disabled is True

        # Verify preview updates for a file
        calc_file = sandbox_dir / "calculator.py"
        app.show_preview(calc_file)
        for _ in range(50):
            await pilot.pause(0.05)
            if "def add" in str(app.query_one("#preview_content").content):
                break
        assert "def add" in str(app.query_one("#preview_content").content)
        assert app.query_one("#open_file_btn").disabled is False

        # Simulate pressing 'm' to toggle mirror/stream mode
        await pilot.press("m")
        assert app.mirror_mode is True
        
        # Simulate pressing 'm' again to revert
        await pilot.press("m")
        assert app.mirror_mode is False
        
        # Quit the app
        await pilot.press("q")

@pytest.mark.asyncio
async def test_tui_recursive_selection(sandbox_dir):
    app = RtxApp(sandbox_dir)
    async with app.run_test() as pilot:
        tree = app.query_one("#dir_tree")
        # Ensure root node is loaded
        await pilot.pause()
        
        # Set cursor to the root directory node
        tree.cursor_line = 0
        node = tree.cursor_node
        assert node is not None
        assert node.data is not None
        assert node.data.path.resolve() == sandbox_dir.resolve()
        
        # Trigger selection of the root directory
        app.action_toggle_select()
        await pilot.pause()
        
        # Root node directory and its descendants should be selected
        assert len(app.selected_paths) > 0
        assert sandbox_dir.resolve() in app.selected_paths
        
        # Verify descendants (e.g. calculator.py) are selected
        calc_file = (sandbox_dir / "calculator.py").resolve()
        assert calc_file in app.selected_paths
        
        # Toggle select again to deselect everything
        app.action_toggle_select()
        await pilot.pause()
        assert len(app.selected_paths) == 0

@pytest.mark.asyncio
async def test_tui_already_indexed_pdf(sandbox_dir):
    # 1. Create a PDF file in sandbox_dir
    pdf_path = (sandbox_dir / "tui_test_doc.pdf").resolve()
    import fitz
    doc_pdf = fitz.open()
    page = doc_pdf.new_page()
    page.insert_text((50, 50), "PDF content", fontsize=12)
    doc_pdf.save(pdf_path)
    
    # 2. Simulate mirror index of it in .rtx/
    rtx_dir = sandbox_dir / ".rtx"
    rtx_dir.mkdir(exist_ok=True)
    mirror_pdf = rtx_dir / "tui_test_doc.pdf.md"
    mirror_pdf.write_text("Parsed PDF content", encoding="utf-8")
    
    app = RtxApp(sandbox_dir)
    try:
        async with app.run_test() as pilot:
            # Directly add to selected paths to avoid navigating the directory tree
            app.selected_paths.add(pdf_path)
            
            # Start parsing - this should trigger the ConfirmPdfScreen
            app.action_start_parsing()
            await pilot.pause()
            
            # Verify that the ConfirmPdfScreen is the current screen
            from rtx.tui import ConfirmPdfScreen
            assert isinstance(app.screen, ConfirmPdfScreen)
            
            # Dismiss the confirmation screen with False (skip re-scan)
            app.screen.dismiss(False)
            await pilot.pause()
            
            # Since we skipped the only selected file, it should notify that no files are left
            # Verify it dismissed and we are back on the main screen
            assert not isinstance(app.screen, ConfirmPdfScreen)
    finally:
        if pdf_path.exists():
            pdf_path.unlink()
        import shutil
        if rtx_dir.exists():
            shutil.rmtree(rtx_dir)


@pytest.mark.asyncio
async def test_tui_vim_navigation(sandbox_dir):
    app = RtxApp(sandbox_dir)
    async with app.run_test() as pilot:
        # Check initial focus
        tree = app.query_one("#dir_tree")
        assert app.focused == tree
        
        # Test Vim focus preview (Shift+L / L)
        await pilot.press("shift+l")
        await pilot.pause()
        assert app.focused != tree
        
        # Test Vim focus tree (Shift+H / H)
        await pilot.press("shift+h")
        await pilot.pause()
        assert app.focused == tree



