# NXTLVL Vercel + Supabase Go-Live Guide

This project is now prepared for Vercel + Supabase.

Production storage uses Supabase Postgres through the `DATABASE_URL` environment variable.
Local development still works with `bookings.db` when `DATABASE_URL` is not set.

## Files Added Or Updated For Deployment

- `booking.py`: uses Supabase/Postgres in production and SQLite locally.
- `api/index.py`: Vercel Python/FastAPI entrypoint.
- `vercel.json`: routes all requests through the FastAPI app.
- `supabase_schema.sql`: SQL table setup for Supabase.
- `.env.example`: list of environment variables to add in Vercel.
- `.gitignore`: keeps local secrets and database files out of Git.

## Step 1: Create The Supabase Project

Why: Vercel is good for hosting the site/API, but bookings need a real persistent database. Supabase gives us that database.

1. Go to `https://supabase.com`.
2. Sign in or create an account.
3. Click `New project`.
4. Organization: choose your personal/default organization.
5. Project name: `nxtlvl`.
6. Database password: create a strong password and save it somewhere safe.
7. Region: choose a US region if available.
8. Click `Create new project`.
9. Wait for Supabase to finish provisioning the project.

## Step 2: Create The Bookings Table

Why: this creates the place where booking requests are stored.

1. In Supabase, open your `nxtlvl` project.
2. In the left sidebar, click `SQL Editor`.
3. Click `New query`.
4. Open this local file: `supabase_schema.sql`.
5. Paste the whole SQL file into the Supabase SQL editor.
6. Click `Run`.
7. You should see success/no error.
8. In the left sidebar, click `Table Editor`.
9. Confirm there is a table named `bookings`.

## Step 3: Get DATABASE_URL From Supabase

Why: this secret string lets the Vercel app connect to your Supabase database.

1. In Supabase, open your `nxtlvl` project.
2. Click `Connect` near the top of the project dashboard.
3. Look for a Postgres connection string.
4. Prefer `Transaction pooler` for Vercel/serverless.
5. Copy the connection string.
6. Replace `[YOUR-PASSWORD]` with the database password you created in Step 1.

It should look roughly like this:

```text
postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

Keep this private.

## Step 4: Create A GitHub Repo

Why: Vercel deploys most smoothly from GitHub.

1. Go to `https://github.com/new`.
2. Repository name: `nxtlvl`.
3. Visibility: private is fine.
4. Do not add a README from GitHub if you are uploading this existing folder.
5. Create the repository.
6. Upload/push the project files from this folder.

Do not upload:

- `.venv`
- `.env`
- `bookings.db`
- `bookings.db-wal`
- `bookings.db-shm`

The `.gitignore` file is set up to avoid those.

## Step 5: Create The Vercel Project

Why: this hosts the actual website.

1. Go to `https://vercel.com`.
2. Sign in with GitHub.
3. Click `Add New...`.
4. Click `Project`.
5. Import the `nxtlvl` GitHub repo.
6. Framework preset: leave as `Other` if Vercel does not detect one.
7. Root directory: the folder that contains `index.html`, `booking.py`, `vercel.json`, and `api/index.py`.
8. Do not deploy yet if Vercel shows an environment variables section first. Add the variables in Step 6.

## Step 6: Add Environment Variables In Vercel

Why: secrets do not live in code. Vercel stores them securely and gives them to the app at runtime.

In Vercel:

1. Open your project.
2. Go to `Settings`.
3. Click `Environment Variables`.
4. Add each variable below.
5. Select all environments: `Production`, `Preview`, and `Development` unless you have a reason not to.
6. Save each one.

Required:

```text
DATABASE_URL=your-full-supabase-connection-string
NXTLVL_ADMIN_KEY=your-private-admin-key
SITE_URL=https://nxtlvl-theta.vercel.app
```

Recommended for email alerts:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_FROM_NAME=NXTLVL Training
SMTP_USER=your-sending-email-address
SMTP_PASS=your-sending-email-app-password
NOTIFY_EMAIL=raquanbryant18@gmail.com
```

Important: `NOTIFY_EMAIL` is where booking alerts go. `SMTP_USER` is the inbox that sends the emails.
They do not have to be the same email address.

If you do not have access to `raquanbryant18@gmail.com`, do not use it as `SMTP_USER`.
Use an email account you can log into, or use a sending service such as Resend.
The site will still send every booking alert to `raquanbryant18@gmail.com` through `NOTIFY_EMAIL`.

Optional SMS alerts:

```text
TWILIO_SID=
TWILIO_TOKEN=
TWILIO_FROM=
NOTIFY_PHONE=+19105079984
```

## Step 7: How To Create NXTLVL_ADMIN_KEY

Why: this is the password/key you enter on `/admin.html`.

Create something long and private. Example format:

```text
nxtlvl-admin-REPLACE-WITH-LONG-RANDOM-TEXT
```

Save it in a password manager or private note. If you lose it, you can replace it in Vercel and redeploy.

## Step 8: How To Create SMTP_PASS For Gmail

Why: Gmail will not let apps send email using your normal password. You need an app password.

Only do this for an email inbox you can access.

1. Go to `https://myaccount.google.com/security`.
2. Log into the email account you want to send from.
3. Make sure `2-Step Verification` is on.
4. Search the page for `App passwords`.
5. Create an app password for Mail.
6. Copy the generated app password.
7. Put that email address in Vercel as `SMTP_USER`.
8. Put the app password in Vercel as `SMTP_PASS`.
9. Keep `NOTIFY_EMAIL=raquanbryant18@gmail.com`.

## Step 9: Deploy

1. In Vercel, click `Deploy`.
2. Wait for the build/deployment to finish.
3. Open the Vercel deployment URL.
4. If it fails, open Vercel project `Logs` and check the error.

## Step 10: Test The Booking System On Vercel

Use the Vercel URL first, before connecting your custom domain.

1. Open the public site.
2. Scroll to booking.
3. Pick a future weekday.
4. Select a time.
5. Submit a test booking using your own email/phone.
6. Confirm the success panel appears.
7. Confirm the selected time disappears from that day.
8. Try to book the same day/time again.
9. Confirm it says the slot is already booked.
10. Open `/admin.html`.
11. Enter your `NXTLVL_ADMIN_KEY`.
12. Confirm the booking appears.
13. Cancel the test booking.
14. Return to the public booking calendar.
15. Confirm the cancelled slot appears again.

## Step 11: Test Supabase

Why: this confirms bookings are stored in the real production database.

1. In Supabase, open your project.
2. Click `Table Editor`.
3. Open the `bookings` table.
4. Confirm your test booking row appeared.
5. Confirm status changes when you cancel/confirm in admin.

## Step 12: Test Notifications

1. Add the email variables in Vercel.
2. Redeploy the latest Vercel deployment so the variables are available.
3. Check notification config:

```bash
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://nxtlvl-theta.vercel.app/admin/notifications/status
```

4. Send a test notification:

```bash
curl -X POST -H "X-Admin-Key: YOUR_ADMIN_KEY" https://nxtlvl-theta.vercel.app/admin/notifications/test
```

5. Check `NOTIFY_EMAIL` inbox.
6. If no email arrives, check Vercel logs.
7. If using Twilio, check your phone for SMS.
8. Submit a real test booking and confirm the customer confirmation email arrives.

## Step 13: Test Payments

The site displays:

- Zelle: `910-507-9984`
- Venmo: `@Raquan-Bryant-1`

Before going public:

1. Click the Venmo link from the deployed site.
2. Confirm it opens the correct Venmo account.
3. Send a small Venmo test payment.
4. Send a small Zelle test payment to `+1 910 507 9984`.
5. Confirm both arrive.

## Step 14: Connect Your Domain

1. In Vercel, open the project.
2. Go to `Settings`.
3. Click `Domains`.
4. Add your domain.
5. Vercel will show DNS records to add.
6. Go to your domain registrar.
7. Add the DNS records exactly as Vercel shows them.
8. Wait for Vercel to show the domain as valid.
9. Open the `https://` version of your domain.
10. Run one final booking test on the real domain.

## Helpful Official Docs

- Vercel FastAPI/Python: `https://vercel.com/docs/frameworks/backend/fastapi`
- Vercel environment variables: `https://vercel.com/docs/environment-variables`
- Supabase connection strings: `https://supabase.com/docs/reference/postgres/connection-strings`
- Supabase SQL editor: `https://supabase.com/docs/guides/database/overview`
- Vercel deployment protection: `https://vercel.com/docs/deployment-protection`
