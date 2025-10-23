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


### Create the Cloud Run Function "project" 
1. Go to **Cloud Run Functions**
1. Click **Services** in the side bar.
1. Along the top find the **(...) Write a function link**
1. Choose **Use an inline editor to create a function** (you could alternatively choose the GitHub option)
1. Give your service a name.
1. Choose a region near your moodle instance.
1. Set the endpoint to **Python 3.10**
1. Choose **Allow Public Access** during initial set up for ease of testing. (Later you will lock it down)
1. Click **Create**.

### Copy the files into the Function "project" 
1. Replace the **requirements.txt** and **main.py** file contents with the file contents from this repo.
1. Add an **app.py** file like the one in this repo.
1. Change the function entrypoint to **linkedinposter**
1. Click **Save and redeploy**

### Add Links from Cloud Run to your Secrets
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

### Test Setup So Far
1. Back on the Deploy Revision interface, go to the bottom and click **Deploy**. It will likely fail saying something like $${\color{red}The\space service\space account\space used\space must\space be\space granted\space the\space 'Secret\space Manager\space Secret\space Accessor'\space role}$$

### Create a Service Account 
1. After the redeployment has failed, use 🖊️ **Edit & deploy new revision** near the top of the page again.
1. You are on the **Containers** MAIN tab. Switch to the **Security** tab. 
1. In the **Service Account** field, choose **Create new service account**.
1. A sidebar will open and the default name will match your Cloud Run "project" name. I always add a dash and "sa" for Service Account.
1. Click Create.
2. In the Step 2 area add roles: **Cloud Run Invoker, Secret Manager Secret Accessor**
4. Switching your focus back to the main Service Details interface, click Deploy. There should be no errors this time. 

### Test Cloud Run
1. Find the service URL. It will be your Cloud run name, a hashed number, your region, and run.app.
1. Copy and paste the URL somewhere you can easily edit it.
2. Go to the Linkedin developers page and inside your LinkedIn app, find the Auth tab and in the OAuth section add your service URL plus **/auth/linkedin/callback** as an Authorized Redirect URL. 
1. Using the service URL again, add **/auth/linkedin/start?badgeid=aero-101&verifcode=FAKECODE** to the end of the url (instead of /auth/linkedin/callback) 
1. Copy and paste the whole thing into a browswer tab address bar and click **enter**.
1. A LinkedIn login screen should appear. After logging in you should see a button. Click the button and view the post created by this service. The verification will not work bc FAKECODE is not a real certificate but the other link should work. When this service is paired with the Moodle plugin, a real certificate code is passed along and can be verified.

### Update the INGRESS SETTINGS
1. You have to use gcloud for this unfortunately.
1. gcloud auth login
1. Set your project:  gcloud config set project PROJECT_NAME
1. SET IT:
   # set service ingress explicitly
  gcloud run services update post-as-function \
     --region=us-west1 \
     --ingress=internal-and-cloud-load-balancing
1. CHECK IT:   
   gcloud run services describe mtl --region=us-west1 \
   --format='table(
    metadata.annotations["run.googleapis.com/ingress-status"],
    spec.template.metadata.annotations["run.googleapis.com/ingress"]
   )'
1. gcloud run services describe mtl --region=us-west1 \
  --format='value(spec.template.metadata.annotations["run.googleapis.com/ingress"])'
1. When the ingress settings are confirmed, there is still no change to the UI bu that's okay. 

## LOAD BALANCER
### CREATE NEG AND BACKEND SERVICE
NEG - Network Endpoint Group
Name your NEG the same as your service plus a dash and neg.

NEG_NAME=mtl-neg
BACKEND=mtl-backend
REGION=us-west1
SERVICE=mtl


gcloud compute network-endpoint-groups create $NEG_NAME \
  --region=$REGION \
  --network-endpoint-type=serverless \
  --cloud-run-service=$SERVICE

if asked, choose to enable compute.googleapis.com

gcloud compute backend-services create $BACKEND \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --protocol=HTTP \
  --region=$REGION

gcloud compute backend-services add-backend $BACKEND \
  --region=$REGION \
  --network-endpoint-group=$NEG_NAME \
  --network-endpoint-group-region=$REGION

### Set up the DNS Record
# Reserve an external regional IP
IP_NAME=mtl-ip

**--Set it up**
gcloud compute addresses create $IP_NAME --region=$REGION
IP_ADDR=$(gcloud compute addresses describe $IP_NAME --region=$REGION --format='value(address)')

**--Read it back**
gcloud compute addresses describe $IP_NAME \
  --region=$REGION --format="get(address)"

 Mine is 136.117.77.40
1. In the DNS provider, under my bintiholdings.com domain, I create an A record with:
   Host: mts
    Type: A
    Value: 136.117.77.40 
    TTL: 300
1. After propogation you can run: dig mtl.bintiholdings.com +short

### CREATE THE URL MAP, THE HTTPS PROXY, the CERT and a FORWARDING RULE
HOST=mtl.bintiholdings.com
URLMAP=mtl-urlmap
PROXY=mtl-https-proxy
CERT=mtl-cert
FWR=mtl-fw
AUTH=mtl-auth
LOCATION=global

# Create DNS authorization (will output a TXT record to add at your DNS)
gcloud certificate-manager dns-authorizations create $AUTH \
  --domain=$HOST \
  --location=global
  
# After adding the TXT and it propagates, create the regional managed cert:
**FOR SOME REASON THIS ONE NEEDS THINGS IN QUOTES**

gcloud certificate-manager dns-authorizations create mtl-auth \
  --domain="mtl.bintioldings.com" \
  --location="global"

If you are asked about enableing certificatemanager.googleapis.com, say yes
  
**--GET BACK THE INFO FOR THE DNS RECORD**
gcloud certificate-manager dns-authorizations describe mtl-auth --location=global

**MY RECORD**
createTime: '2025-10-23T23:02:28.914237250Z'
dnsResourceRecord:
  data: 8b4533d1-8349-4192-ad4c-6afea982cfb9.8.authorize.certificatemanager.goog.
  name: _acme-challenge.mtl.bintioldings.com.
  type: CNAME
domain: mtl.bintioldings.com
name: projects/static-groove-476019-a5/locations/global/dnsAuthorizations/mtl-auth
type: FIXED_RECORD
updateTime: '2025-10-23T23:02:29.300491667Z'



CONFIRM by looking
gcloud certificate-manager certificates list


  
# After adding the TXT and it propagates, create the regional managed cert:
gcloud certificate-manager certificates create $CERT \
  --domains=$HOST \
  --dns-authorizations=$AUTH \
  --region=$REGION







# URL map (default routes to your backend)
gcloud compute url-maps create $URLMAP \
  --default-service=$BACKEND \
  --region=$REGION

# Managed cert for your domain (DNS A/AAAA must point to the LB IP; cert will auto-provision)
# Create DNS authorization (will output a TXT record to add at your DNS)
gcloud certificate-manager dns-authorizations create $AUTH \
  --domain=$HOST --region=$REGION

gcloud compute ssl-certificates create $CERT \
  --domains=$HOST \
  --region=$REGION

# HTTPS proxy
gcloud compute region-target-https-proxies create $PROXY \
  --url-map=$URLMAP \
  --ssl-certificates=$CERT \
  --region=$REGION

gcloud compute networks subnets create proxy-only-$REGION \
  --purpose=REGIONAL_MANAGED_PROXY \
  --role=ACTIVE \
  --region=$REGION \
  --network=default \
  --range=10.129.0.0/23



# Forwarding rule (443)
gcloud compute forwarding-rules create $FWR \
  --address=$IP_NAME \
  --target-https-proxy=$PROXY \
  --ports=443 \
  --region=$REGION



## SECURING THE PROCESS
1. Once the above is working, test it by triggering it from moodle. You will need to go into the Moodle Site Admin Plugins page and find the Local section and click on **LinkedIn Share for Certificates** in the Gateway Endpoint field. put your SERVICE URL again (nothing added to the end) TODO - or do we add auth/linkedin/start (will depend on final solution.
2. Test the process end to end by triggering the share from the course banner share button. If it works, it's time to lock it down.
3. We have tried JWT tokens, and a gateway. Now we are trying restricted ingress. We'll have to see what happens. 
1. When everything is working and you don't want anyone hitting the service url directly you can run: 
gcloud run services update mtl --region=us-west1 --no-default-url
1. gcloud run services describe mtl --region=us-west1 \
  --format='value(metadata.annotations["run.googleapis.com/ingress-status"])'
# expected: internal-and-cloud-load-balancing
1. 


