## **LINKEDIN DEVELOPER ACCOUNT AND APP**
1. Begin by signing up for a LinkedIn developer account. 
1. On the https://www.linkedin.com/developers/apps?appStatus=active select **Create App**. and fill out the form.
1. When the app you created opens, choose the **Auth** tab at the top and **Create a Client Secret**. You will enter the id and secret into **Google Cloud Secrets Manager**.
1. On the **Products** tab add the **Share on Linkedin** and **Sign In with LinkedIn using OpenID Connect** products or scopes. 


## **IN GOOGLE CLOUD CONSOLE**
1. Create a project. 


## **IN GOOGLE CLOUD CONSOLE - WITH YOUR NEW PROJECT SELECTED**
### Secret Manager
1. Go to **Secret Manager**
1. Click **+ Create Secret**
    1. Name the secret **LINKEDIN_CLIENT_ID** and copy/paste the id from Linkedin into the secret value field.
    2. Click Create Secret
1. Repeat the process to set up a **LINKEDIN_CLIENT_SECRET** secret  (add the secret from above).
1. Repeat the process to set up a **FLASK_SECRET** (this is an encryption thing)
1. TODO - add info on how to create the flask secret.


### Cloud Run
1. Go to **Cloud Run**
1. Click **Services** in the side bar.
1. Along the top find the **(...) Write a function link**
1. Choose **Use an inline editor to create a function** (you could alternatively choose the GitHub option)
1. GIve your service a name.
1. Choose a region near your moodle instance.
1. Set the endpoint to **Python 3.10**
1. Choose **Allow Public Access** during initial set up for ease of testing. (Later you will lock it down)
1. Click **Create**.
1. Replace the **requirements.txt** and **main.py** file contents with the file contents from this repo.
1. Add an **app.py** file like the one in this repo.
1. Change the function entrypoint to **linkedinposter**
1. Click **Save and redeploy**
1. After the redeployment is complete, find 🖊️ **Edit & deploy new revision** near the top of the page and click it.
1. You are on the **Containers** MAIN tab. 
1. Halfway down the **Containers** page look for the blue second-level "tab" called **Settings**. Choose **Variables & Secrets** (tag next to it)
1. Click the **+ Reference as secret** button. Create three secrets, link them to the secrets you set up earlier and give them the exact same names. Set them all to "**latest**."
1. At the top of the page, next to the **Containers** tab, choose **Security**.
1. In the **Service Account** field choose **Create a new service account**.
1. The suggest name for the service account will match your cloud run name, add a dash and sa for service account to the end (optional)
1. Click Create.
1. Add Roles **Secret Manager Secret Accessor** and **Cloud Run Invoker** to the service account.
1. Click **Done**.
1. Back on the Deploy Revision interface, go to the bottom and click **Deploy**.

## Test Cloud Run
1. Find the service URL. It will be your Cloud run name, a hashed number, your region, and run.app.
1. Copy and paste the URL somewhere you can easily edit it. 
1. Add /auth/linkedin/start?badgeid=aero-101&verifcode=FAKECODE to the end of the url. 
1. Copy and paste the whole thing into a browswer tab address bar and click enter. 


