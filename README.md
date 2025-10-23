**LINKEDIN DEVELOPER ACCOUNT AND APP**
1.Begin by signing up for a LinkedIn developer account. 
1. On the https://www.linkedin.com/developers/apps?appStatus=active select **Create App.** and fill out the form.
1. When the app you created opens, choose the **Auth** tab at the top and create a Client Secret. You will need the id and secret for your Cloud Run project.
1. On the **Products** tab add the **Share on Linkedin** and **Sign In with LinkedIn using OpenID Connect** products or scopes. 

**IN GOOGLE CLOUD CONSOLE**
Create a project. 

**IN GOOGLE CLOUD CONSOLE - WITH YOUR NEW PROJECT SELECTED**
Go to Secrets Manager and set up a LINKEDIN_CLIENT_ID secret (add the secret from above). 
Set up a LINKEDIN_CLIENT_SECRET secret and add the secret from above.
Set up a FLASK_SECRET (this is an encryption thing) TODO - add info on how to create.


If you are posting on behalf of a workplace, your company's LinkedIn page owner will need to supply you with the org id.
which you will input into the linkedin.com/developers interface. 
