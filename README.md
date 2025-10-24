## **LINKEDIN DEVELOPER ACCOUNT AND APP**
1. Begin by signing up for a LinkedIn developer account. 
1. On the https://www.linkedin.com/developers/apps?appStatus=active select **Create App**. and fill out the form.
1. When the app you created opens, choose the **Auth** tab at the top and **Create a Client Secret**. You will enter the id and secret into **Google Cloud Secrets Manager**.
1. On the **Products** tab add the **Share on Linkedin** and **Sign In with LinkedIn using OpenID Connect** products or scopes. 


## **IN GOOGLE CLOUD CONSOLE**
### Create a Project
1. Create a project, give it a name, make note of the ID. 

### Secret Manager
1. Go to **Secret Manager**
1. Click **+ Create Secret**
    1. Name the secret **LINKEDIN_CLIENT_ID** and copy/paste the id from Linkedin into the secret value field.
    2. Click Create Secret
1. Repeat the process to set up a **LINKEDIN_CLIENT_SECRET** secret  (add the secret from above).
1. Repeat the process to set up a **FLASK_SECRET** (this is an encryption thing)
1. TODO - add info on how to create the flask secret.


### Create the Cloud Run Function (Your function will be called the SERVICE throughout these instructions)
1. Go to **Cloud Run Functions**
1. Click **Services** in the side bar.
1. Along the top find the **(...) Write a function link**
1. Choose **Use an inline editor to create a function** (you could alternatively choose the GitHub option)
1. Give your service a name.
1. Choose a region near your moodle instance.
1. Set the endpoint to **Python 3.10**
1. Choose **Allow Public Access** during initial set up for ease of testing. (Later you will lock it down)
1. Click **Create**.

### Copy the files into the Function/Service
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
1. Find the service URL. It will be your Cloud run name, a hashed number, your region, and "run.app".
1. Copy and paste the URL somewhere you can easily edit it.
1. Go to the Linkedin developers page and inside your LinkedIn app, find the **Auth** tab and in the **OAuth** section add your service URL plus **/auth/linkedin/callback** as an Authorized Redirect URL. 
1. Using the service URL again, add **/auth/linkedin/start?badgeid=aero-101&verifcode=FAKECODE** to the end of the url (instead of /auth/linkedin/callback) You can leave it saying FAKECODE -- that's a valid code for testing. 
1. Copy and paste the whole thing into a browswer tab address bar and click **enter**.
1. A LinkedIn login screen should appear. After logging in you should see a button. Click the button and view the post created by this service. When this service is paired with the Moodle plugin, a real certificate code is passed along and can be verified.

### Update the INGRESS SETTINGS
1. You have to use gcloud for this unfortunately.
    ```
   gcloud auth login
    ```
1. Run this command to set 3 variables: 
    ```PROJECT_ID = 'static-groove-476019-a5'
       REGION="us-west1"
       SERVICE="mtl"
    ```
1. Set your project as context for future commands:
     ```
   gcloud config set project $PROJECT_ID
     ```
   
1. **SET THE INGRESS POLICY:**
   ```
   gcloud run services update $SERVICE \
     --region=$REGION \
     --ingress=internal-and-cloud-load-balancing
   ```
1. **CHECK THAT THE INGRESS POLICY IS IN EFFECT** 
   ```
   gcloud run services describe $SERVICE --region=$REGION \
   --format='table(
    metadata.annotations["run.googleapis.com/ingress-status"],
    spec.template.metadata.annotations["run.googleapis.com/ingress"]
   )'
   ```
1. **YOU CAN ALSO CHECK THEM BY NAME**
   ```
    gcloud run services describe $SERVICE --region=$REGION \
      --format='value(spec.template.metadata.annotations["run.googleapis.com/ingress"])'
   ```
## LOAD BALANCER
- NEG - Network Endpoint Group
- Name your NEG the same as your service plus a dash and neg.

1. **SET MORE SESSION VARIABLES**
    ```
    NEG_NAME=${SERVICE}-"neg" 
    BACKEND=${SERVICE}-backend
    ```

1. **Create your Network Endpoint Group**
    ```
    gcloud compute network-endpoint-groups create $NEG_NAME \
      --region=$REGION \
      --network-endpoint-type=serverless \
      --cloud-run-service=$SERVICE
    ```

1. If asked, choose to **enable compute.googleapis.com**

1. **Create Your Backend Service**
    ```
    gcloud compute backend-services create $BACKEND \
      --load-balancing-scheme=EXTERNAL_MANAGED \
      --protocol=HTTP \
      --region=$REGION
    ```

1. **Connect Your NEG to your Backend Service**
    ```
    gcloud compute backend-services add-backend $BACKEND \
      --region=$REGION \
      --network-endpoint-group=$NEG_NAME \
      --network-endpoint-group-region=$REGION
    ```

## Set up the DNS Record 
1. **Create an IP Variable**
    ```
    IP_NAME=mtl-ip
    ```
1. **Reserve an external regional IP**
    ```
    gcloud compute addresses create $IP_NAME --region=$REGION
    ```
1. **Read it back**
    ```
    gcloud compute addresses describe $IP_NAME \
      --region=$REGION --format="get(address)"
    ```

1. **Assign your reserved IP to a new variable**
    ```
    IP_ADDR=$(gcloud compute addresses describe $IP_NAME --region=$REGION --format='value(address)')
    ```
- Mine is 136.117.77.40

## YOUR DOMAIN AND DNS MANAGER (for me it's Bluehost)
1. In the DNS provider, under the correct domain, I create an A record with:
   - Host: mts
   - Type: A
   - Value: 136.117.77.40 
   - TTL: 300
1. After propogation you can run:
    ```
         dig mtl.bintiholdings.com +short
    ```

## BACK TO GOOGLE CLOUD
### CREATE THE DNS AUTHS, RECORDS and CERTIFICATE
- It is really important to do this through the UI. The CLI will send you in endless circles. 
1. Go to **Certificates** in GCP
1. **Enable** the Cert Mgr API
1. When the Cert Manager UI appears, click **Create Certificate**
1. Name your cert **mtl-regional-cert**, choose **Regional** and set region to your service region (for me it's us-west1)
1. Choose a **Google-managed certificate**
1. Add the domain landing address you are using as the entry point for your load-balancer - for me its mtl.bintiholdings.com
1. Auth type is DNS Auth and VERY IMPORTANT - click** Create Missing DNS Authorization **before hitting the CREATE button. **Approve** in sidebar.
1. Click **Create** to Complete your Certificate. 
1. The row will show **Active** column with a green circle and checkmark when the DNS record is set up correctly.
1. Click back into the Certificate to get the info you need to create your second DNS record. 

## BACK TO YOUR DOMAIN AND DNS MANAGER (for me it's Bluehost)
### CREATE ANOTHER CNAME RECORD 
- projects/static-groove-476019-a5/locations/us-west1/dnsAuthorizations/dns-authz-mtl-bintiholdings-com
- DNS Record type: CNAME
- DNS Record name: _acme-challenge_fupu3vphu27nw5vk.mtl.bintiholdings.com.
- DNS Record data: 51d52b85-feca-441b-b2d9-ebb88ef9c692.2.us-west1.authorize.certificatemanager.goog.

## BACK TO GOOGLE CLOUD
### CREATE THE URL MAP, THE VPC/SUBNET, THE HTTPS PROXY, THE CERT and a FORWARDING RULE
    ```
    HOST=${SERVICE}-bintiholdings.com
    URLMAP=${SERVICE}-urlmap
    ```

### URL map (default routes to your backend)
1. CREATE THE URL MAP:
    ```
    gcloud compute url-maps create $URLMAP \
      --default-service=$BACKEND \
      --region=$REGION
    ```
1. Check the map's details:
    ```  
    gcloud compute url-maps describe mtl-urlmap --region=$REGION
    ```

### CREATE VPC, SUMNET, HTTPS proxy
1. Create Some Variables
    ```
    LB_NAME=mtl-lb
    NETWORK=mtl-lb-network
    TARGET_PROXY=mtl-http-proxy
    FORWARDING_RULE=mtl-fw-rule-80
    FR2=mtl-fw-rule-443
    ```
    
1. **Create VPC**
    ```
    gcloud compute networks create $NETWORK --subnet-mode=custom
    ```
1. **Check that the VPC was created**
   ```
   gcloud compute networks list
    ```
1. **Use the UI to Create the proxy-only subnet inside the VPC**
- Locate the VPC you just created and click into it
- Choose the Subnets tab
- Click + Add Subnet
- In the sidebar: Name it mtl-lb-network-subnet
- Choose your region.
- Choose Regional Managed Proxy
- Choose Active
- Leave box unchecked I guess?
- Paste 10.129.0.0/23 into IPv4 Range
- Click Add
- Your subnet should appear under Reserved proxy-only subnets for load balancing

### Create Network Services including the Load Balancer, the NEG, proxies and forwarding rules

1. **Create target HTTP proxy**
   ```   
    gcloud compute target-http-proxies create $TARGET_PROXY \
    --region=$REGION \
    --url-map=$URLMAP
   ```
1. **Check the proxy details**
    ```
    gcloud compute target-http-proxies list
    ```

1. **Create forwarding rule for HTTP (port 80)**
    ```   
    gcloud compute forwarding-rules create $FORWARDING_RULE \
        --region=$REGION \
        --load-balancing-scheme=EXTERNAL_MANAGED \
        --address=mtl-ip \
        --target-http-proxy=$TARGET_PROXY \
        --ports=80
    ```
    
# Forwarding rule (443)
```gcloud compute forwarding-rules create $FWR \
  --address=mtl-ip \
  --target-https-proxy=$PROXY \
  --ports=443 \
  --region=$REGION```



## SECURING THE PROCESS
1. Once the above is working, test it by triggering it from moodle. You will need to go into the Moodle Site Admin Plugins page and find the Local section and click on **LinkedIn Share for Certificates** in the Gateway Endpoint field. put your SERVICE URL again (nothing added to the end) TODO - or do we add auth/linkedin/start (will depend on final solution.
1. Test the process end to end by triggering the share from the course banner share button. If it works, it's time to lock it down.
1. We have tried JWT tokens, and a gateway. Now we are trying restricted ingress. We'll have to see what happens. 
1. When everything is working and you don't want anyone hitting the service url directly you can run: 
```gcloud run services update mtl --region=us-west1 --no-default-url```
1. ```gcloud run services describe mtl --region=us-west1 \
  --format='value(metadata.annotations["run.googleapis.com/ingress-status"])'```
# expected: internal-and-cloud-load-balancing
1. 


