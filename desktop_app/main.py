"""
Desktop App for Academy Automation
Fetches classes from ACA2000, students, Naver emails, and finds missing homework submissions.
"""
import dearpygui.dearpygui as dpg
import json
import sys
import os
import threading
from datetime import datetime, timedelta, date

# Add parent directory to path to import utils (only when running as script)
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Lazy import: utils loads selenium etc. — defer so the window appears instantly
_utils = None
def _load_utils():
    global _utils
    if _utils is None:
        import utils
        _utils = utils
    return _utils

# Global state
class_info = {}
aca_driver = None
config = {}


def load_config():
    """Load credentials from config.json (next to the exe or script)"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(__file__)

    config_path = os.path.join(base_path, "config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def log(msg):
    """Add message to output"""
    current = dpg.get_value("output_text")
    dpg.set_value("output_text", current + msg + "\n")


def set_status(msg):
    """Update status"""
    dpg.set_value("status_text", f"Status: {msg}")


def fetch_classes_callback():
    """Fetch classes from ACA2000"""
    global class_info, aca_driver

    dpg.set_value("output_text", "")
    set_status("Connecting to ACA2000...")
    log("[Step 1] Fetching classes from ACA2000...")

    # Clean up previous driver
    if aca_driver:
        try:
            aca_driver.quit()
        except Exception:
            pass

    try:
        result = _load_utils().get_class_list_from_aca2000(
            headless=False,
            cust_num=config.get("ACA2000_CUST_NUM"),
            user_id=config.get("ACA2000_ID"),
            user_pw=config.get("ACA2000_PW"),
        )

        if result and result[0]:
            class_info = result[0]
            aca_driver = result[1]

            log(f"Found {len(class_info)} classes:")
            for name in class_info.keys():
                log(f"  - {name}")

            # Create checkboxes for classes
            if dpg.does_item_exist("class_group"):
                dpg.delete_item("class_group", children_only=True)

            for name in class_info.keys():
                dpg.add_checkbox(label=name, tag=f"class_{name}", parent="class_group")

            dpg.show_item("class_frame")
            dpg.show_item("run_btn")
            set_status(f"Found {len(class_info)} classes. Select and click 'Find Missing Homework'.")

            try:
                aca_driver.minimize_window()
            except Exception:
                pass
        else:
            log("No classes found or connection failed.")
            set_status("Failed to fetch classes.")

    except Exception as e:
        log(f"Error: {e}")
        set_status("Error fetching classes.")


def select_all_callback(sender, app_data):
    """Toggle all checkboxes"""
    for name in class_info.keys():
        dpg.set_value(f"class_{name}", app_data)


def run_automation_callback():
    """Run the full automation"""
    global class_info, aca_driver

    # Get selected classes
    selected = [name for name in class_info.keys() if dpg.get_value(f"class_{name}")]

    if not selected:
        log("Please select at least one class.")
        return

    if not config.get("NAVER_ID") or not config.get("NAVER_PW"):
        log("Naver credentials not found in config.json!")
        return

    dpg.disable_item("fetch_btn")
    dpg.disable_item("run_btn")

    try:
        log("\n" + "=" * 50)
        log("[Step 2] Running Automation...")
        log("=" * 50)

        selected_class_ids = {name: class_info[name] for name in selected}

        # Fetch students
        set_status("Fetching students...")
        log(f"\nFetching students for {len(selected)} classes...")

        driver = aca_driver

        if not driver:
            log("ACA2000 session expired. Please fetch classes again.")
            set_status("Session expired.")
            return

        student_list = _load_utils().get_students_for_classes(driver, selected_class_ids)
        total_students = sum(len(s) for s in student_list.values())
        log(f"Found {total_students} students in {len(student_list)} classes")

        # Fetch Naver emails
        set_status("Fetching Naver emails... (may need manual 2FA)")
        log("\nFetching Naver emails...")
        log("(If 2FA is required, please complete it in the browser)")

        # Parse date range from UI
        try:
            sd = datetime.strptime(dpg.get_value("start_date"), "%Y-%m-%d").date()
            ed = datetime.strptime(dpg.get_value("end_date"), "%Y-%m-%d").date()
        except ValueError:
            sd, ed = None, None
            log("Invalid date format, using default (last 7 days)")

        emails = _load_utils().fetch_naver_email(
            headless=False,
            naver_id=config["NAVER_ID"],
            naver_passkey=config["NAVER_PW"],
            start_date=sd,
            end_date=ed
        )
        senders = {e["sender"] for e in emails}
        log(f"Found {len(emails)} emails from {len(senders)} senders")

        # Compare
        set_status("Comparing students against emails...")
        log("\nComparing students against emails...")

        results = _load_utils().find_missing_students(student_list, emails)
        total_missing = sum(len(r["missing"]) for r in results.values())

        # Display Results
        log("\n" + "=" * 50)
        log("RESULTS")
        log("=" * 50)

        for class_name, data in results.items():
            log(f"\n[{class_name}]")
            if data["matched"]:
                for student, subject in data["matched"]:
                    log(f"  OK {student} -> {subject}")
            if data["missing"]:
                for s in data["missing"]:
                    log(f"  XX {s}")

        # Summary
        log("\n" + "=" * 50)
        if total_missing > 0:
            log(f"MISSING HOMEWORK: {total_missing} students")
            log("=" * 50)
            for class_name, data in results.items():
                if data["missing"]:
                    log(f"\n[{class_name}]")
                    for s in data["missing"]:
                        log(f"  - {s}")
        else:
            log("All students submitted homework!")

        set_status("Done!")
        log("\n" + "=" * 50)
        log("COMPLETE!")

    except Exception as e:
        log(f"\nError: {e}")
        import traceback
        log(traceback.format_exc())
        set_status("Error during automation.")

    finally:
        dpg.enable_item("fetch_btn")
        dpg.enable_item("run_btn")
        # Reset
        class_info = {}
        aca_driver = None
        dpg.hide_item("class_frame")
        dpg.hide_item("run_btn")


def main():
    global config

    # Load config
    config = load_config()
    if not config:
        print("ERROR: config.json not found or invalid!")
        print("Please create config.json next to the app with your credentials.")
        input("Press Enter to exit...")
        return

    # Create context
    dpg.create_context()

    # Add Korean font support
    import platform
    with dpg.font_registry():
        if platform.system() == "Darwin":  # macOS
            font_path = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
        elif platform.system() == "Windows":
            font_path = "C:/Windows/Fonts/malgun.ttf"
        else:  # Linux
            font_path = "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"

        try:
            with dpg.font(font_path, 16) as korean_font:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Korean)
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
            dpg.bind_font(korean_font)
        except Exception as e:
            print(f"Warning: Could not load Korean font: {e}")

    # Create window
    with dpg.window(label="Academy Automation", tag="main_window"):
        dpg.add_text("Academy Automation", tag="title")
        dpg.add_text("Status: Ready", tag="status_text")
        dpg.add_separator()

        # Step 1: Fetch Classes
        dpg.add_button(label="1. Fetch Classes from ACA2000", callback=fetch_classes_callback, tag="fetch_btn")

        # Class selection (initially hidden)
        with dpg.group(tag="class_frame", show=False):
            dpg.add_text("Select Classes:")
            with dpg.group(tag="class_group"):
                pass  # Checkboxes added dynamically
            dpg.add_checkbox(label="Select All", callback=select_all_callback)

        # Date range for email filtering
        with dpg.group(horizontal=True):
            dpg.add_text("Email date range:")
            default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            default_end = datetime.now().strftime("%Y-%m-%d")
            dpg.add_input_text(label="Start", tag="start_date", default_value=default_start, width=100)
            dpg.add_input_text(label="End", tag="end_date", default_value=default_end, width=100)

        # Step 2: Run automation (initially hidden)
        dpg.add_button(label="2. Find Missing Homework", callback=run_automation_callback, tag="run_btn", show=False)

        dpg.add_separator()

        # Results
        dpg.add_text("Results:")
        dpg.add_input_text(
            tag="output_text",
            multiline=True,
            readonly=True,
            width=650,
            height=400,
            default_value=""
        )

    # Setup and run
    dpg.create_viewport(title="Academy Automation", width=700, height=600)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()

    # Cleanup
    if aca_driver:
        try:
            aca_driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
