## OVERVIEW
The full solution requires:

- A Moodle Plug in (different repo)
- A LinkedIn Developer App 
- A GCP Cloud Run Serverless Function
- A GCP Load Balancer
- A Domain Management Service to Assign a domain or subdomain address

## Recommended Order:
- Detailed instructions are available on other pages in this repo

### PHASE 1:
- Create your LinkedIn App 
- Create your GCP Cloud Run Function
- Test it to make sure you can sign in and post.

## PHASE 2:
- Create your Load Balancer to accept HTTP (not HTTPS, yet)
- Test it to ensure it flows from the LB through to posting

## PHASE 3:
- Add HTTPS handing to the Load Balancer
- Create the DNS entries and Certificates needed
- Test it for HTTPS traffic
  
