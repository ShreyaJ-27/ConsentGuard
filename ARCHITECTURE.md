# ConsentGuard Architecture

ConsentGuard uses a **layered defense model** combining request analysis, consent verification, output scanning, provenance labelling, and victim support workflows.

---

## 🏗️ System Components
- **Input Layer**: User request + uploaded image/video  
- **Request Filter**: Multilingual prompt analysis (English, Hindi, Hinglish)  
- **Consent Engine**: Identity verification via live selfie or permission proof  
- **Output Scanner**: Detects harmful combinations (real face + nudity)  
- **Labelling & Provenance**: Adds AI-generated watermark + hidden tracking metadata  
- **Enforcement Module**: Blocks repeat offenders, escalates to human review  
- **Victim Support Tool**: Generates evidence packs, takedown requests, and cybercrime complaints  

---

## 🔄 Workflow Diagram

```mermaid
flowchart TD
    A[User Request] --> B[Request Check: Multilingual Filter]
    B -->|Suspicious| C[Consent Verification]
    C -->|No Consent| X[Block Output]
    C -->|Consent Verified| D[AI Generation]
    D --> E[Result Scan: Harmful Content Detection]
    E -->|Harmful| X[Block Output]
    E -->|Safe| F[Label & Provenance]
    F --> G[Deliver Output to User]
    B --> H[Repeat Attempts Monitor]
    H --> I[Human Reviewer + Evidence Pack]
    
    subgraph Victim Workflow
        V1[Victim Uploads Fake] --> V2[Local Scan & Fingerprint]
        V2 --> V3[Evidence Pack Generation]
        V3 --> V4[Takedown Request + Cybercrime Complaint]
    end
