import logging
import os
import time
from datetime import datetime

import click
import schedule
from dotenv import load_dotenv, set_key
from InquirerPy import inquirer, prompt
from playwright.sync_api import Playwright, TimeoutError, sync_playwright
from pync import Notifier

log_path = os.path.dirname(__file__)
# Create logs directory if it doesn't exist
os.makedirs(os.path.join(log_path, "logs"), exist_ok=True)
os.makedirs(os.path.join(log_path, "debug_screenshot"), exist_ok=True)
# Generate a timestamped log file name
log_filename = datetime.now().strftime("logs/log_%Y-%m-%d_%H-%M-%S.log")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Could also use INFO, WARNING, ERROR, CRITICAL
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_path, log_filename)),  # Log to file
        logging.StreamHandler(),  # Print logs to console
    ],
)


def load_env_variables():
    """Load environment variables."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path=env_path)
    return {
        "email": os.getenv("EMAIL"),
        "password": os.getenv("PASSWORD"),
        "signature": os.getenv("SIGNATURE"),
        "url": os.getenv("URL"),
        "positions": os.getenv("POSITIONS"),
    }


def save_to_env(env_path, data):
    """Save key-value pairs to the .env file."""
    for key, value in data.items():
        set_key(env_path, key.upper(), (value or "").strip())


@click.command(name="set-credentials")
def set_credentials():
    """
    Prompt the user to input any missing credentials.

    This function checks if email, password, and signature are present in the credentials
    dictionary. For any missing values, it prompts the user to provide input.

    Args:
        credentials (dict): A dictionary containing user credentials with keys:
            'email', 'password', and 'signature'. Values may be None or empty strings.

    Returns:
        dict: The updated credentials dictionary with any missing values filled in
              by user input.
    """
    """Prompt user for missing credentials."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    credentials = load_env_variables()

    credentials["email"] = inquirer.text(message="Enter your email").execute()

    credentials["password"] = inquirer.secret(message="Enter your password").execute()

    credentials["signature"] = inquirer.text(message="Enter your signature").execute()
    save_to_env(env_path, credentials)
    click.echo(
        "Credentials saved to .env file. You can now run the script without entering them again."
    )
    return credentials


@click.command(name="set-registration")
def set_registration():
    """
    Main function to execute the script for Open Play registration.

    This function handles the entire registration process for Gotham volleyball open play events by:
    1. Loading environment variables for credentials
    2. Prompting the user for the event URL and preferred positions
    3. Requesting any missing credentials from the user
    4. Saving credentials to the .env file
    5. Launching a Playwright automated browser session to complete the registration

    No parameters required as all inputs are collected through interactive prompts.

    Dependencies:
        - os
        - PyInquirer (prompt)
        - python-dotenv (for .env file handling)
        - playwright

    Returns:
        None
    """
    """Main function to execute the script for Open Play registration."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")

    results = prompt(
        [
            {
                "type": "input",
                "message": "Enter the url of the event you want to register for",
                "name": "url",
                "multiline": False,
            },
            {
                "type": "checkbox",
                "name": "positions",
                "message": "Select your positions (select with spacebar)",
                "choices": ["Setter", "Outside", "Middle", "Opposite"],
            },
        ]
    )

    credentials = load_env_variables()

    for key, value in results.items():
        if key == "positions":
            value = ",".join(value)
        credentials[key] = value

    save_to_env(env_path, credentials)


def handle_registration(page, framePage, email, password, signature, positions):
    """
    Handles the registration process on the specified webpage.

    This function automates the process of registering a user by interacting with
    various elements on the webpage, such as filling out forms, checking checkboxes,
    and submitting the registration form.

    Args:
        page (playwright.sync_api.Page): The main Playwright page object used for navigation and interaction.
        framePage (playwright.sync_api.Frame): The frame within the page where registration elements are located.
        email (str): The email address to be used for registration.
        password (str): The password to be used for registration.
        signature (str): The electronic signature to be entered during the registration process.
        positions (str): A comma-separated string of positions to be selected during registration.

    Steps:
        1. Clicks the "Register" link and navigates to the registration page.
        2. Signs in using LeagueApps by filling in the email and password fields.
        3. Selects eligibility and position checkboxes based on the provided input.
        4. Accepts all waivers by checking the corresponding checkboxes.
        5. Fills in the electronic signature field and submits the registration form.

    Raises:
        playwright.sync_api.Error: If any interaction with the webpage fails.
    """
    """Handle the registration process."""
    framePage.get_by_role("link", name="Register").click()
    framePage.locator("#reg-fa").click()
    page.wait_for_timeout(2000)
    page.get_by_role("link", name="Sign in with LeagueApps").click()

    page.get_by_role("textbox", name="Email").click()
    page.get_by_role("textbox", name="Email").fill(email)
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Sign in with LeagueApps").click()

    framePage.locator('input[type="checkbox"][value="I am eligible"]').check()
    for position in positions.split(","):
        framePage.locator(f'input[type="checkbox"][value={position}]').check()

    framePage.get_by_text("Next", exact=True).click()

    framePage.locator('label[for="waiver-accept-cb-0"]').check()
    framePage.locator('label[for="waiver-accept-cb-1"]').check()
    framePage.locator('label[for="waiver-accept-cb-2"]').check()

    framePage.locator("#electronicSignature").click()
    framePage.locator("#electronicSignature").fill(signature)
    framePage.locator("#register-submit").click()
    Notifier.notify(
        "You have successfully registered for Open Play.",
        title="Registration Complete",
    )


def launch_registration_process(playwright: Playwright, credentials):
    """Run the Playwright automation."""
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    try:
        response = page.goto(credentials["url"])
        if response.status not in [200, 202]:
            logging.error(f"Page not found: {credentials['url']}")
            page.screenshot(path="error_screenshot.png")
            return

        page.wait_for_selector("iframe")
        framePage = page.frame_locator("#monolith-iframe")
        if not framePage.get_by_role("link", name="Register").is_visible():
            if framePage.locator(
                'a[class~="btn"][class~="large-btn"][class~="disabled"]'
            ).is_visible():
                Notifier.notify(
                    "Open Play is at capacity.",
                    title="Registration Status",
                )
                logging.info("Open Play is at capacity")
            elif (
                framePage.locator("a.btn.right:has-text('Pay Now')").is_visible()
                or framePage.locator("em.site-notice:has-text('Sold Out')").is_visible()
            ):
                Notifier.notify(
                    "You are already registered or sold out.",
                    title="Registration Status",
                )
                logging.info("Already registered or sold out")
            else:
                Notifier.notify(
                    "Open Play registration link not found.",
                    title="Registration Error",
                )
                logging.error("Register link not found")
            page.screenshot(
                path=os.path.join(log_path, "debug_screenshot", "error_screenshot.png")
            )
            return

        handle_registration(
            page,
            framePage,
            credentials["email"],
            credentials["password"],
            credentials["signature"],
            credentials["positions"],
        )

    except TimeoutError as e:
        logging.error(f"TimeoutError: {e}")
        page.screenshot(
            path=os.path.join(log_path, "debug_screenshot", "error_screenshot.png")
        )
        logging.info("Screenshot saved as error_screenshot.png")
    finally:
        context.close()
        browser.close()


def clear_url():
    """Clear the URL in the .env file."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    set_key(env_path, "URL", "")
    logging.info("URL cleared from .env file.")


def run_automation():
    credentials = set_credentials()
    """Execute the registration process using Playwright."""
    with sync_playwright() as playwright:
        launch_registration_process(playwright, credentials)

    clear_url()
    return schedule.CancelJob


@click.command(name="run")
def schedule_registration():
    set_registration()
    schedule.every().friday.at("12:00").do(run_automation)
    while 1:
        n = schedule.idle_seconds()
        if n is None:
            # no more jobs
            break
        elif n > 0:
            # sleep exactly the right amount of time
            time.sleep(n)
        schedule.run_pending()
