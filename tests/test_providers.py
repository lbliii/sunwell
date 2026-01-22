"""Tests for Files, Projects, Git, Bookmarks, Habits, and Contacts providers (RFC-078)."""

from pathlib import Path

import pytest

from sunwell.providers.native.bookmarks import SunwellBookmarks
from sunwell.providers.native.contacts import SunwellContacts
from sunwell.providers.native.files import SunwellFiles
from sunwell.providers.native.git import SunwellGit
from sunwell.providers.native.habits import SunwellHabits
from sunwell.providers.native.projects import SunwellProjects


class TestSunwellFiles:
    """Tests for the SunwellFiles provider."""

    @pytest.fixture
    def temp_workspace(self, tmp_path: Path) -> Path:
        """Create a temporary workspace with test files."""
        # Create some test files
        (tmp_path / "file1.py").write_text("print('hello')")
        (tmp_path / "file2.js").write_text("console.log('hello')")
        (tmp_path / "readme.md").write_text("# Test Project")

        # Create a subdirectory
        subdir = tmp_path / "src"
        subdir.mkdir()
        (subdir / "main.py").write_text("def main(): pass")
        (subdir / "utils.py").write_text("def helper(): pass")

        return tmp_path

    @pytest.fixture
    def files_provider(self, temp_workspace: Path) -> SunwellFiles:
        """Create a files provider for testing."""
        return SunwellFiles(temp_workspace)

    async def test_list_files_non_recursive(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test listing files non-recursively."""
        files = await files_provider.list_files(".")
        names = {f.name for f in files}

        assert "file1.py" in names
        assert "file2.js" in names
        assert "readme.md" in names
        assert "src" in names  # Directory included
        # Nested files should not be included
        assert "main.py" not in names

    async def test_list_files_recursive(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test listing files recursively."""
        files = await files_provider.list_files(".", recursive=True)
        names = {f.name for f in files}

        assert "file1.py" in names
        assert "main.py" in names
        assert "utils.py" in names

    async def test_list_files_subdirectory(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test listing files in a subdirectory."""
        files = await files_provider.list_files("src")
        names = {f.name for f in files}

        assert "main.py" in names
        assert "utils.py" in names
        assert "file1.py" not in names

    async def test_search_files_by_extension(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test searching files by extension pattern."""
        files = await files_provider.search_files("*.py")
        names = {f.name for f in files}

        assert "file1.py" in names
        assert "main.py" in names
        assert "file2.js" not in names

    async def test_search_files_by_substring(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test searching files by name substring."""
        files = await files_provider.search_files("main")
        names = {f.name for f in files}

        assert "main.py" in names

    async def test_read_file(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test reading file contents."""
        content = await files_provider.read_file("file1.py")
        assert content == "print('hello')"

    async def test_read_file_not_found(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test reading non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            await files_provider.read_file("nonexistent.txt")

    async def test_get_metadata(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test getting file metadata."""
        metadata = await files_provider.get_metadata("file1.py")

        assert metadata is not None
        assert metadata.name == "file1.py"
        assert metadata.extension == "py"
        assert metadata.is_directory is False
        assert metadata.size > 0

    async def test_get_metadata_not_found(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test getting metadata for non-existent file returns None."""
        metadata = await files_provider.get_metadata("nonexistent.txt")
        assert metadata is None

    async def test_file_info_to_dict(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test FileInfo serialization."""
        metadata = await files_provider.get_metadata("file1.py")
        assert metadata is not None

        data = metadata.to_dict()
        assert data["name"] == "file1.py"
        assert data["extension"] == "py"
        assert data["is_directory"] is False

    async def test_path_security(
        self, files_provider: SunwellFiles
    ) -> None:
        """Test that paths can't escape workspace root."""
        with pytest.raises(ValueError, match="escapes workspace root"):
            await files_provider.read_file("../../../etc/passwd")


class TestSunwellProjects:
    """Tests for the SunwellProjects provider."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path: Path) -> Path:
        """Create a temporary data directory."""
        data_dir = tmp_path / ".sunwell"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def projects_provider(self, temp_data_dir: Path) -> SunwellProjects:
        """Create a projects provider for testing."""
        return SunwellProjects(temp_data_dir)

    async def test_list_projects_empty(
        self, projects_provider: SunwellProjects
    ) -> None:
        """Test listing projects when none exist."""
        projects = await projects_provider.list_projects()
        assert projects == []

    async def test_add_and_list_project(
        self, projects_provider: SunwellProjects, tmp_path: Path
    ) -> None:
        """Test adding and listing a project."""
        project = await projects_provider.add_project(
            str(tmp_path / "my-project"),
            name="My Project",
            description="Test project",
        )

        assert project.name == "My Project"
        assert project.description == "Test project"
        assert project.status == "active"

        projects = await projects_provider.list_projects()
        assert len(projects) == 1
        assert projects[0].name == "My Project"

    async def test_get_project(
        self, projects_provider: SunwellProjects, tmp_path: Path
    ) -> None:
        """Test getting a specific project."""
        path = str(tmp_path / "test-project")
        await projects_provider.add_project(path, name="Test")

        project = await projects_provider.get_project(path)
        assert project is not None
        assert project.name == "Test"

    async def test_get_project_not_found(
        self, projects_provider: SunwellProjects
    ) -> None:
        """Test getting non-existent project returns None."""
        project = await projects_provider.get_project("/nonexistent/path")
        assert project is None

    async def test_search_projects(
        self, projects_provider: SunwellProjects, tmp_path: Path
    ) -> None:
        """Test searching projects by name."""
        await projects_provider.add_project(
            str(tmp_path / "frontend-app"), name="Frontend App"
        )
        await projects_provider.add_project(
            str(tmp_path / "backend-api"), name="Backend API"
        )

        # Search by name
        results = await projects_provider.search_projects("frontend")
        assert len(results) == 1
        assert results[0].name == "Frontend App"

        # Search that matches both
        results = await projects_provider.search_projects("app")
        assert len(results) == 1  # Only "Frontend App" contains "app"

    async def test_update_last_opened(
        self, projects_provider: SunwellProjects, tmp_path: Path
    ) -> None:
        """Test updating last_opened timestamp."""
        path = str(tmp_path / "project")
        project1 = await projects_provider.add_project(path)
        original_time = project1.last_opened

        # Small delay to ensure time difference
        import time
        time.sleep(0.01)

        project2 = await projects_provider.update_last_opened(path)
        assert project2 is not None
        assert project2.last_opened >= original_time

    async def test_archive_project(
        self, projects_provider: SunwellProjects, tmp_path: Path
    ) -> None:
        """Test archiving a project."""
        path = str(tmp_path / "to-archive")
        await projects_provider.add_project(path)

        project = await projects_provider.archive_project(path)
        assert project is not None
        assert project.status == "archived"

    async def test_project_to_dict(
        self, projects_provider: SunwellProjects, tmp_path: Path
    ) -> None:
        """Test Project serialization."""
        await projects_provider.add_project(
            str(tmp_path / "test"),
            name="Test",
            description="A test",
        )

        projects = await projects_provider.list_projects()
        data = projects[0].to_dict()

        assert data["name"] == "Test"
        assert data["description"] == "A test"
        assert data["status"] == "active"
        assert "last_opened" in data


class TestSunwellGit:
    """Tests for the SunwellGit provider."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> Path:
        """Create a temporary git repository."""
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo,
            capture_output=True,
        )

        # Create initial commit
        (repo / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo,
            capture_output=True,
        )

        return repo

    @pytest.fixture
    def git_provider(self, git_repo: Path) -> SunwellGit:
        """Create a git provider for testing."""
        return SunwellGit(git_repo)

    async def test_get_status_clean(self, git_provider: SunwellGit) -> None:
        """Test getting status of a clean repo."""
        status = await git_provider.get_status()

        assert status.is_clean
        assert len(status.files) == 0
        # Branch could be 'main' or 'master' depending on git config
        assert status.branch in ("main", "master")

    async def test_get_status_with_changes(
        self, git_provider: SunwellGit, git_repo: Path
    ) -> None:
        """Test getting status with uncommitted changes."""
        # Make a change
        (git_repo / "new_file.txt").write_text("new content")

        status = await git_provider.get_status()

        assert not status.is_clean
        assert len(status.files) > 0
        # Should have an untracked file
        file_paths = [f.path for f in status.files]
        assert "new_file.txt" in file_paths

    async def test_get_log(self, git_provider: SunwellGit) -> None:
        """Test getting commit log."""
        commits = await git_provider.get_log(limit=10)

        assert len(commits) >= 1
        assert commits[0].message == "Initial commit"
        assert commits[0].author == "Test User"
        assert commits[0].email == "test@test.com"

    async def test_get_branches(self, git_provider: SunwellGit) -> None:
        """Test getting branches."""
        branches = await git_provider.get_branches()

        local_branches = [b for b in branches if not b.is_remote]
        assert len(local_branches) >= 1

        # Current branch should be marked
        current = next((b for b in branches if b.is_current), None)
        assert current is not None

    async def test_get_diff_clean(self, git_provider: SunwellGit) -> None:
        """Test getting diff with no changes."""
        diff = await git_provider.get_diff()
        assert diff == ""

    async def test_get_diff_with_changes(
        self, git_provider: SunwellGit, git_repo: Path
    ) -> None:
        """Test getting diff with changes."""
        # Modify a tracked file
        (git_repo / "README.md").write_text("# Modified")

        diff = await git_provider.get_diff()
        assert "README.md" in diff or "Modified" in diff

    async def test_search_commits(
        self, git_provider: SunwellGit, git_repo: Path
    ) -> None:
        """Test searching commits."""
        import subprocess

        # Add another commit
        (git_repo / "feature.py").write_text("# Feature code")
        subprocess.run(["git", "add", "feature.py"], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add feature implementation"],
            cwd=git_repo,
            capture_output=True,
        )

        # Search for commits
        results = await git_provider.search_commits("feature")
        assert len(results) >= 1
        assert any("feature" in c.message.lower() for c in results)

    async def test_git_status_to_dict(self, git_provider: SunwellGit) -> None:
        """Test GitStatus serialization."""
        status = await git_provider.get_status()
        data = status.to_dict()

        assert "branch" in data
        assert "is_clean" in data
        assert "files" in data
        assert isinstance(data["files"], list)

    async def test_git_commit_to_dict(self, git_provider: SunwellGit) -> None:
        """Test GitCommit serialization."""
        commits = await git_provider.get_log(limit=1)
        assert len(commits) > 0

        data = commits[0].to_dict()
        assert "hash" in data
        assert "short_hash" in data
        assert "author" in data
        assert "message" in data
        assert "date" in data


class TestSunwellBookmarks:
    """Tests for the SunwellBookmarks provider."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path: Path) -> Path:
        """Create a temporary data directory."""
        data_dir = tmp_path / ".sunwell"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def bookmarks_provider(self, temp_data_dir: Path) -> SunwellBookmarks:
        """Create a bookmarks provider for testing."""
        return SunwellBookmarks(temp_data_dir)

    async def test_add_bookmark(
        self, bookmarks_provider: SunwellBookmarks
    ) -> None:
        """Test adding a bookmark."""
        bookmark = await bookmarks_provider.add_bookmark(
            url="https://example.com",
            title="Example Site",
            tags=["test", "example"],
            description="An example website",
        )

        assert bookmark.url == "https://example.com"
        assert bookmark.title == "Example Site"
        assert "test" in bookmark.tags
        assert "example" in bookmark.tags
        assert bookmark.description == "An example website"

    async def test_search_bookmarks(
        self, bookmarks_provider: SunwellBookmarks
    ) -> None:
        """Test searching bookmarks."""
        await bookmarks_provider.add_bookmark(
            url="https://python.org",
            title="Python Official",
            tags=["programming", "python"],
        )
        await bookmarks_provider.add_bookmark(
            url="https://rust-lang.org",
            title="Rust Language",
            tags=["programming", "rust"],
        )

        # Search by title
        results = await bookmarks_provider.search("python")
        assert len(results) == 1
        assert results[0].title == "Python Official"

        # Search by tag
        results = await bookmarks_provider.search("programming")
        assert len(results) == 2

    async def test_get_by_tag(
        self, bookmarks_provider: SunwellBookmarks
    ) -> None:
        """Test getting bookmarks by tag."""
        await bookmarks_provider.add_bookmark(
            url="https://docs.python.org",
            title="Python Docs",
            tags=["documentation", "python"],
        )
        await bookmarks_provider.add_bookmark(
            url="https://doc.rust-lang.org",
            title="Rust Docs",
            tags=["documentation", "rust"],
        )

        results = await bookmarks_provider.get_by_tag("documentation")
        assert len(results) == 2

        results = await bookmarks_provider.get_by_tag("python")
        assert len(results) == 1
        assert results[0].title == "Python Docs"

    async def test_get_all_tags(
        self, bookmarks_provider: SunwellBookmarks
    ) -> None:
        """Test getting all unique tags."""
        await bookmarks_provider.add_bookmark(
            url="https://a.com", title="A", tags=["web", "tools"]
        )
        await bookmarks_provider.add_bookmark(
            url="https://b.com", title="B", tags=["tools", "dev"]
        )

        tags = await bookmarks_provider.get_all_tags()
        assert set(tags) == {"web", "tools", "dev"}

    async def test_delete_bookmark(
        self, bookmarks_provider: SunwellBookmarks
    ) -> None:
        """Test deleting a bookmark."""
        bookmark = await bookmarks_provider.add_bookmark(
            url="https://delete-me.com",
            title="Delete Me",
        )

        # Verify it exists
        results = await bookmarks_provider.search("delete")
        assert len(results) == 1

        # Delete it
        deleted = await bookmarks_provider.delete_bookmark(bookmark.id)
        assert deleted

        # Verify it's gone
        results = await bookmarks_provider.search("delete")
        assert len(results) == 0

    async def test_get_recent(
        self, bookmarks_provider: SunwellBookmarks
    ) -> None:
        """Test getting recent bookmarks."""
        # Add several bookmarks
        for i in range(5):
            await bookmarks_provider.add_bookmark(
                url=f"https://site{i}.com",
                title=f"Site {i}",
            )

        recent = await bookmarks_provider.get_recent(limit=3)
        assert len(recent) == 3

    async def test_bookmark_update_on_duplicate_url(
        self, bookmarks_provider: SunwellBookmarks
    ) -> None:
        """Test that adding a duplicate URL updates the existing bookmark."""
        # Add initial bookmark
        await bookmarks_provider.add_bookmark(
            url="https://example.com",
            title="Original Title",
            tags=["original"],
        )

        # Add same URL with different title
        await bookmarks_provider.add_bookmark(
            url="https://example.com",
            title="Updated Title",
            tags=["updated"],
        )

        # Should only have one bookmark
        results = await bookmarks_provider.search("example")
        assert len(results) == 1
        assert results[0].title == "Updated Title"

    async def test_bookmark_to_dict(
        self, bookmarks_provider: SunwellBookmarks
    ) -> None:
        """Test Bookmark serialization."""
        bookmark = await bookmarks_provider.add_bookmark(
            url="https://test.com",
            title="Test",
            tags=["tag1", "tag2"],
        )

        data = bookmark.to_dict()
        assert data["url"] == "https://test.com"
        assert data["title"] == "Test"
        assert data["tags"] == ["tag1", "tag2"]


# =============================================================================
# HABITS PROVIDER TESTS (RFC-078 Phase 4)
# =============================================================================


class TestSunwellHabits:
    """Tests for the SunwellHabits provider."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path: Path) -> Path:
        """Create a temporary data directory."""
        data_dir = tmp_path / ".sunwell"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def habits_provider(self, temp_data_dir: Path) -> SunwellHabits:
        """Create a habits provider for testing."""
        return SunwellHabits(temp_data_dir)

    async def test_create_habit(self, habits_provider: SunwellHabits) -> None:
        """Test creating a new habit."""
        habit = await habits_provider.create_habit(
            name="Exercise",
            description="Daily workout",
            frequency="daily",
            target_count=1,
        )

        assert habit.name == "Exercise"
        assert habit.description == "Daily workout"
        assert habit.frequency == "daily"
        assert habit.target_count == 1
        assert habit.id is not None

    async def test_list_habits(self, habits_provider: SunwellHabits) -> None:
        """Test listing habits."""
        await habits_provider.create_habit(name="Habit 1")
        await habits_provider.create_habit(name="Habit 2")

        habits = await habits_provider.list_habits()
        assert len(habits) == 2

    async def test_get_habit(self, habits_provider: SunwellHabits) -> None:
        """Test getting a specific habit."""
        created = await habits_provider.create_habit(name="Test Habit")

        habit = await habits_provider.get_habit(created.id)
        assert habit is not None
        assert habit.name == "Test Habit"

    async def test_archive_habit(self, habits_provider: SunwellHabits) -> None:
        """Test archiving a habit."""
        habit = await habits_provider.create_habit(name="To Archive")

        # Archive it
        archived = await habits_provider.archive_habit(habit.id)
        assert archived is not None
        assert archived.archived is True

        # Should not appear in default list
        habits = await habits_provider.list_habits()
        assert len(habits) == 0

        # Should appear with include_archived
        habits = await habits_provider.list_habits(include_archived=True)
        assert len(habits) == 1

    async def test_log_entry(self, habits_provider: SunwellHabits) -> None:
        """Test logging a habit entry."""
        habit = await habits_provider.create_habit(name="Log Test")

        entry = await habits_provider.log_entry(habit.id, count=1, notes="Done!")
        assert entry.habit_id == habit.id
        assert entry.count == 1
        assert entry.notes == "Done!"

    async def test_get_entries(self, habits_provider: SunwellHabits) -> None:
        """Test getting entries for a habit."""
        habit = await habits_provider.create_habit(name="Entry Test")

        # Log multiple entries
        await habits_provider.log_entry(habit.id, count=1)
        await habits_provider.log_entry(habit.id, count=2)

        entries = await habits_provider.get_entries(habit.id)
        # Both should merge into one entry for today
        assert len(entries) == 1
        assert entries[0].count == 3  # 1 + 2

    async def test_get_streak(self, habits_provider: SunwellHabits) -> None:
        """Test getting streak for a habit."""
        habit = await habits_provider.create_habit(name="Streak Test")

        # Log entry for today
        await habits_provider.log_entry(habit.id)

        streak = await habits_provider.get_streak(habit.id)
        assert streak == 1

    async def test_habit_to_dict(self, habits_provider: SunwellHabits) -> None:
        """Test Habit serialization."""
        habit = await habits_provider.create_habit(
            name="Test",
            description="Description",
            frequency="weekly",
            target_count=3,
        )

        data = habit.to_dict()
        assert data["name"] == "Test"
        assert data["description"] == "Description"
        assert data["frequency"] == "weekly"
        assert data["target_count"] == 3


# =============================================================================
# CONTACTS PROVIDER TESTS (RFC-078 Phase 4)
# =============================================================================


class TestSunwellContacts:
    """Tests for the SunwellContacts provider."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path: Path) -> Path:
        """Create a temporary data directory."""
        data_dir = tmp_path / ".sunwell"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def contacts_provider(self, temp_data_dir: Path) -> SunwellContacts:
        """Create a contacts provider for testing."""
        from sunwell.providers.native.contacts import SunwellContacts
        return SunwellContacts(temp_data_dir)

    async def test_create_contact(self, contacts_provider: SunwellContacts) -> None:
        """Test creating a new contact."""
        contact = await contacts_provider.create_contact(
            name="John Doe",
            email="john@example.com",
            phone="+1234567890",
            organization="ACME Corp",
            tags=["work", "important"],
        )

        assert contact.name == "John Doe"
        assert contact.email == "john@example.com"
        assert contact.phone == "+1234567890"
        assert contact.organization == "ACME Corp"
        assert "work" in contact.tags

    async def test_list_contacts(self, contacts_provider: SunwellContacts) -> None:
        """Test listing contacts."""
        await contacts_provider.create_contact(name="Alice")
        await contacts_provider.create_contact(name="Bob")

        contacts = await contacts_provider.list_contacts()
        assert len(contacts) == 2
        # Should be sorted by name
        assert contacts[0].name == "Alice"
        assert contacts[1].name == "Bob"

    async def test_get_contact(self, contacts_provider: SunwellContacts) -> None:
        """Test getting a specific contact."""
        created = await contacts_provider.create_contact(name="Test Contact")

        contact = await contacts_provider.get_contact(created.id)
        assert contact is not None
        assert contact.name == "Test Contact"

    async def test_search_contacts(self, contacts_provider: SunwellContacts) -> None:
        """Test searching contacts."""
        await contacts_provider.create_contact(name="John Smith", email="john@example.com")
        await contacts_provider.create_contact(name="Jane Doe", organization="Smith & Co")

        # Search by name
        results = await contacts_provider.search("john")
        assert len(results) == 1
        assert results[0].name == "John Smith"

        # Search by organization
        results = await contacts_provider.search("smith")
        assert len(results) == 2

    async def test_get_by_tag(self, contacts_provider: SunwellContacts) -> None:
        """Test getting contacts by tag."""
        await contacts_provider.create_contact(name="Work Contact", tags=["work"])
        await contacts_provider.create_contact(name="Personal Contact", tags=["personal"])

        work_contacts = await contacts_provider.get_by_tag("work")
        assert len(work_contacts) == 1
        assert work_contacts[0].name == "Work Contact"

    async def test_delete_contact(self, contacts_provider: SunwellContacts) -> None:
        """Test deleting a contact."""
        contact = await contacts_provider.create_contact(name="To Delete")

        deleted = await contacts_provider.delete_contact(contact.id)
        assert deleted is True

        # Should be gone
        result = await contacts_provider.get_contact(contact.id)
        assert result is None

    async def test_import_vcard(
        self, contacts_provider: SunwellContacts, tmp_path: Path
    ) -> None:
        """Test importing contacts from vCard."""
        # Create a simple vCard file
        vcard_content = """BEGIN:VCARD
VERSION:3.0
FN:John Doe
EMAIL:john@example.com
TEL:+1234567890
ORG:Test Company
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Jane Smith
EMAIL:jane@example.com
END:VCARD"""

        vcard_path = tmp_path / "contacts.vcf"
        vcard_path.write_text(vcard_content)

        imported = await contacts_provider.import_vcard(vcard_path)
        assert imported == 2

        contacts = await contacts_provider.list_contacts()
        assert len(contacts) == 2

    async def test_export_vcard(self, contacts_provider: SunwellContacts) -> None:
        """Test exporting contacts to vCard."""
        await contacts_provider.create_contact(
            name="Export Test",
            email="export@test.com",
        )

        vcard = await contacts_provider.export_vcard()
        assert "BEGIN:VCARD" in vcard
        assert "FN:Export Test" in vcard
        assert "EMAIL:export@test.com" in vcard

    async def test_contact_to_dict(
        self, contacts_provider: SunwellContacts
    ) -> None:
        """Test Contact serialization."""
        contact = await contacts_provider.create_contact(
            name="Test",
            email="test@example.com",
            tags=["tag1", "tag2"],
        )

        data = contact.to_dict()
        assert data["name"] == "Test"
        assert data["email"] == "test@example.com"
        assert data["tags"] == ["tag1", "tag2"]
